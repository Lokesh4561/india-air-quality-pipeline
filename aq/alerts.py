"""Alerts: unhealthy AQI levels and sudden PM2.5 spikes.

At most one alert of each type per city per day (enforced by a UNIQUE constraint),
so hourly runs never spam duplicates.
"""

from aq.aqi import UNHEALTHY

INSERT_ALERT = """
INSERT INTO aq.alerts (city, ts, alert_day, alert_type, value, message)
VALUES (%s, %s, (%s AT TIME ZONE 'Asia/Kolkata')::date, %s, %s, %s)
ON CONFLICT (city, alert_type, alert_day) DO NOTHING
RETURNING city, alert_type, message
"""

LATEST_AQI = """
SELECT DISTINCT ON (city) city, ts, aqi, category
FROM aq.aqi_hourly
WHERE ts >= now() - interval '3 hours'
ORDER BY city, ts DESC
"""

# Latest hourly PM2.5 compared with the same city's last 7 days (z-score)
PM25_SPIKES = """
WITH latest AS (
    SELECT DISTINCT ON (city) city, ts, pm2_5
    FROM aq.readings
    WHERE ts >= now() - interval '3 hours' AND pm2_5 IS NOT NULL
    ORDER BY city, ts DESC
),
baseline AS (
    SELECT city, avg(pm2_5) AS mean, stddev_samp(pm2_5) AS sd
    FROM aq.readings
    WHERE ts >= now() - interval '7 days' AND ts < now() - interval '3 hours'
    GROUP BY city
)
SELECT l.city, l.ts, l.pm2_5, b.mean, (l.pm2_5 - b.mean) / NULLIF(b.sd, 0) AS z
FROM latest l JOIN baseline b USING (city)
WHERE (l.pm2_5 - b.mean) / NULLIF(b.sd, 0) > %(z)s AND l.pm2_5 > %(min_pm)s
"""


def run(conn, z_threshold: float = 3.0, min_pm25: float = 60.0) -> list[tuple]:
    new_alerts = []
    with conn.cursor() as cur:
        for city, ts, aqi, cat in conn.execute(LATEST_AQI).fetchall():
            if cat in UNHEALTHY:
                msg = f"{city}: AQI {aqi} ({cat}). Sensitive groups should limit outdoor activity."
                cur.execute(INSERT_ALERT, (city, ts, ts, "unhealthy_aqi", aqi, msg))
                new_alerts += cur.fetchall()

        spikes = conn.execute(PM25_SPIKES, {"z": z_threshold, "min_pm": min_pm25}).fetchall()
        for city, ts, pm25, mean, z in spikes:
            msg = f"{city}: PM2.5 spiked to {pm25:.0f} µg/m³ (7-day average {mean:.0f}, z={z:.1f})."
            cur.execute(INSERT_ALERT, (city, ts, ts, "pm25_spike", pm25, msg))
            new_alerts += cur.fetchall()
    return new_alerts
