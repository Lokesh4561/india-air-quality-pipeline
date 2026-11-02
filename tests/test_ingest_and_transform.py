from datetime import datetime, timedelta

import pandas as pd

from aq.config import IST
from aq.ingest import parse_hourly
from aq.transform import rolling_aqi

SAMPLE_PAYLOAD = {
    "timezone": "Asia/Kolkata",
    "hourly": {
        "time": ["2026-11-02T10:00", "2026-11-02T11:00", "2026-11-02T12:00", "2026-11-02T13:00"],
        "pm2_5": [80.0, 85.5, None, 90.0],
        "pm10": [150.0, 160.0, None, 170.0],
        "nitrogen_dioxide": [20.0, 21.0, None, 22.0],
        "ozone": [30.0, 31.0, None, 32.0],
        "sulphur_dioxide": [5.0, 5.0, None, 5.0],
        "carbon_monoxide": [500.0, 510.0, None, 520.0],
    },
}


def test_parse_splits_observed_and_forecast():
    now = datetime(2026, 11, 2, 11, 30, tzinfo=IST)
    observed, forecast = parse_hourly("Delhi", SAMPLE_PAYLOAD, now)

    assert [row[1].hour for row in observed] == [10, 11]
    assert [row[1].hour for row in forecast] == [13]       # 12:00 skipped: all values missing
    assert observed[0][:4] == ("Delhi", datetime(2026, 11, 2, 10, tzinfo=IST), 80.0, 150.0)
    assert forecast[0] == ("Delhi", datetime(2026, 11, 2, 13, tzinfo=IST), now.date(), 90.0, 170.0)


def test_parse_handles_empty_payload():
    assert parse_hourly("Delhi", {}, datetime.now(IST)) == ([], [])


def test_rolling_aqi_needs_16_hours_then_uses_24h_average():
    start = datetime(2026, 11, 1, 0, tzinfo=IST)
    df = pd.DataFrame({
        "city": ["Pune"] * 30,
        "ts": pd.to_datetime([start + timedelta(hours=i) for i in range(30)], utc=True),
        "pm2_5": [45.0] * 30,   # constant 45 -> sub-index 75
        "pm10": [40.0] * 30,    # constant 40 -> sub-index 40
    })
    rows = rolling_aqi(df)

    assert len(rows) == 30 - 15            # first AQI appears at the 16th hour
    city, ts, pm25, pm10, aqi, cat, dominant = rows[0]
    assert (city, pm25, aqi, cat, dominant) == ("Pune", 45.0, 75, "Satisfactory", "pm2_5")
