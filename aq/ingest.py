"""Ingestion: fetch hourly air quality for all cities -> bronze (raw JSON) -> silver (readings, forecasts).

All cities are fetched in ONE batched API request (the API accepts comma-separated
coordinates), which is faster and avoids rate limits on shared CI runners.
Idempotent: readings are upserted on (city, ts) and forecasts on (city, ts, issued_date).
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


def fetch_all(cities, past_days: int, forecast_days: int, retries: int = 4) -> tuple[dict, list[dict]]:
    """Fetch every city in one request; retry with exponential backoff on network errors, 429 or 5xx."""
    params = {
        "latitude": ",".join(str(lat) for _, lat, _ in cities),
        "longitude": ",".join(str(lon) for _, _, lon in cities),
        "hourly": ",".join(POLLUTANTS),
        "timezone": "Asia/Kolkata",
        "past_days": past_days,
        "forecast_days": forecast_days,
    }
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=60)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
            resp.raise_for_status()
            data = resp.json()
            payloads = data if isinstance(data, list) else [data]  # one location returns an object, many a list
            if len(payloads) != len(cities):
                raise ValueError(f"expected {len(cities)} locations, got {len(payloads)}")
            return params, payloads
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            if attempt == retries:
                raise
            wait = 5 * 2 ** (attempt - 1)
            print(f"  API request failed (attempt {attempt}/{retries}), retrying in {wait}s...")
            time.sleep(wait)
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

    try:
        params, payloads = fetch_all(CITIES, past_days, forecast_days)
    except Exception as exc:
        totals["failed"] = len(CITIES)
        print(f"  failed   all cities: {exc}")
        return totals

    for (city, lat, lon), payload in zip(CITIES, payloads):
        observed, forecast = parse_hourly(city, payload, now)
        city_params = {**params, "latitude": lat, "longitude": lon, "batched": True}
        with conn.transaction():
            conn.execute(
                "INSERT INTO aq.raw_responses (city, params, payload) VALUES (%s, %s, %s)",
                (city, Jsonb(city_params), Jsonb(payload)),
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

    return totals
