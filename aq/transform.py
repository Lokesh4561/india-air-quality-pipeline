"""Gold layer: 24-hour rolling averages -> Indian AQI per city per hour."""

import pandas as pd

from aq.aqi import compute_aqi

UPSERT_AQI = """
INSERT INTO aq.aqi_hourly (city, ts, pm2_5_24h, pm10_24h, aqi, category, dominant)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (city, ts) DO UPDATE SET
    pm2_5_24h = EXCLUDED.pm2_5_24h, pm10_24h = EXCLUDED.pm10_24h,
    aqi = EXCLUDED.aqi, category = EXCLUDED.category, dominant = EXCLUDED.dominant
"""

MIN_HOURS_IN_WINDOW = 16  # CPCB requires at least 16 of 24 hourly values for a 24h average


def rolling_aqi(df: pd.DataFrame) -> list[tuple]:
    """Compute AQI rows from a DataFrame with columns city, ts, pm2_5, pm10 (pure function, unit-tested)."""
    rows = []
    for city, group in df.groupby("city"):
        g = group.set_index("ts").sort_index()[["pm2_5", "pm10"]].astype(float)
        rolled = g.rolling("24h", min_periods=MIN_HOURS_IN_WINDOW).mean()
        for ts, r in rolled.iterrows():
            aqi, cat, dominant = compute_aqi(r["pm2_5"], r["pm10"])
            if aqi is None:
                continue
            pm25 = None if pd.isna(r["pm2_5"]) else round(float(r["pm2_5"]), 2)
            pm10 = None if pd.isna(r["pm10"]) else round(float(r["pm10"]), 2)
            rows.append((city, ts.to_pydatetime(), pm25, pm10, aqi, cat, dominant))
    return rows


def run(conn, days: int = 3) -> int:
    """Recompute AQI for the last `days` days (plus 1 day of history for the rolling window)."""
    cur = conn.execute(
        "SELECT city, ts, pm2_5, pm10 FROM aq.readings "
        "WHERE ts >= now() - make_interval(days => %s) ORDER BY city, ts",
        (days + 1,),
    )
    df = pd.DataFrame(cur.fetchall(), columns=["city", "ts", "pm2_5", "pm10"])
    if df.empty:
        return 0
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    rows = rolling_aqi(df)
    with conn.transaction(), conn.cursor() as c:
        c.executemany(UPSERT_AQI, rows)
    return len(rows)
