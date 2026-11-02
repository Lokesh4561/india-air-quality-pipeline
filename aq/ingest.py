"""Ingestion: fetch hourly air quality for each city -> bronze (raw JSON) -> silver (readings, forecasts).

Idempotent: readings are upserted on (city, ts) and forecasts on (city, ts, issued_date),
so re-running the same hour never creates duplicates.
"""

import time
from datetime import datetime

import requests
from psycopg.types.json import Jsonb

from aq.cities import CITIES
from aq.config import API_URL, IST, POLLUTANTS

HEADERS = {"User-Agent": "india-air-quality-pipeline (portfolio project)"}

UPSERT_READING = """
INSERT INTO aq.readings (city, ts, pm2_5, pm10, nitrogen_dioxide, ozone, sulphur_dioxide, carbon_monoxide)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (city, ts) DO UPDATE SET
    pm2_5 = EXCLUDED.pm2_5, pm10 = EXCLUDED.pm10,
    nitrogen_dioxide = EXCLUDED.nitrogen_dioxide, ozone = EXCLUDED.ozone,
    sulphur_dioxide = EXCLUDED.sulphur_dioxide, carbon_monoxide = EXCLUDED.carbon_monoxide,
    ingested_at = now()
"""

UPSERT_FORECAST = """
INSERT INTO aq.forecasts (city, ts, issued_date, pm2_5, pm10)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (city, ts, issued_date) DO UPDATE SET
    pm2_5 = EXCLUDED.pm2_5, pm10 = EXCLUDED.pm10, ingested_at = now()
"""


def fetch_city(lat: float, lon: float, past_days: int, forecast_days: int, retries: int = 3) -> tuple[dict, dict]:
    """Call the Open-Meteo Air Quality API, retrying with backoff on network errors or HTTP 429/5xx."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(POLLUTANTS),
        "timezone": "Asia/Kolkata",
        "past_days": past_days,
        "forecast_days": forecast_days,
    }
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
            resp.raise_for_status()
            return params, resp.json()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            if attempt == retries:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def parse_hourly(city: str, payload: dict, now: datetime) -> tuple[list[tuple], list[tuple]]:
    """Split the API's hourly arrays into observed rows (ts <= now) and forecast rows (ts > now).

    Times arrive as local IST strings like "2026-11-02T14:00"; they are stored timezone-aware.
    Hours where every pollutant is missing are skipped.
    """
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    series = [hourly.get(p, [None] * len(times)) for p in POLLUTANTS]
    issued_date = now.astimezone(IST).date()

    observed, forecast = [], []
    for i, t in enumerate(times):
        values = [s[i] if i < len(s) else None for s in series]
        if all(v is None for v in values):
            continue
        ts = datetime.fromisoformat(t).replace(tzinfo=IST)
        if ts <= now:
            observed.append((city, ts, *values))
        else:
            forecast.append((city, ts, issued_date, values[0], values[1]))  # pm2_5, pm10
    return observed, forecast


def run(conn, past_days: int = 1, forecast_days: int = 2) -> dict:
    """Ingest all cities. Returns counts for logging."""
    now = datetime.now(IST)
    totals = {"cities": 0, "failed": 0, "readings": 0, "forecasts": 0}

    for city, lat, lon in CITIES:
        try:
            params, payload = fetch_city(lat, lon, past_days, forecast_days)
        except Exception as exc:
            totals["failed"] += 1
            print(f"  failed   {city}: {exc}")
            continue

        observed, forecast = parse_hourly(city, payload, now)
        with conn.transaction():
            conn.execute(
                "INSERT INTO aq.raw_responses (city, params, payload) VALUES (%s, %s, %s)",
                (city, Jsonb(params), Jsonb(payload)),
            )
            with conn.cursor() as cur:
                if observed:
                    cur.executemany(UPSERT_READING, observed)
                if forecast:
                    cur.executemany(UPSERT_FORECAST, forecast)

        totals["cities"] += 1
        totals["readings"] += len(observed)
        totals["forecasts"] += len(forecast)
        print(f"  ok       {city:<14} {len(observed):>5} readings  {len(forecast):>4} forecasts")
        time.sleep(0.2)  # be polite to the free API

    return totals
