"""How accurate are air quality forecasts? Compares stored forecasts with what was later observed.

Run with:  python -m aq.forecast_eval
Needs a few days of hourly pipeline runs first (forecasts must "come true" before they can be scored).
"""

from aq.db import get_conn

SQL = """
SELECT ((f.ts AT TIME ZONE 'Asia/Kolkata')::date - f.issued_date) AS lead_days,
       count(*)                                  AS pairs,
       round(avg(abs(f.pm2_5 - r.pm2_5))::numeric, 1) AS mae_pm2_5,
       round(avg(abs(f.pm10  - r.pm10 ))::numeric, 1) AS mae_pm10
FROM aq.forecasts f
JOIN aq.readings  r USING (city, ts)
WHERE f.pm2_5 IS NOT NULL AND r.pm2_5 IS NOT NULL
GROUP BY 1
ORDER BY 1
"""


def main() -> None:
    with get_conn() as conn:
        rows = conn.execute(SQL).fetchall()
    if not rows:
        print("No forecast/actual pairs yet. Let the hourly pipeline run for a few days, then try again.")
        return
    print(f"{'lead (days)':>11} {'pairs':>7} {'MAE PM2.5':>10} {'MAE PM10':>9}")
    for lead, pairs, mae25, mae10 in rows:
        print(f"{lead:>11} {pairs:>7} {mae25:>10} {mae10:>9}")
    print("\nMAE = mean absolute error in µg/m³ (lower is better). Accuracy usually drops as lead time grows.")


if __name__ == "__main__":
    main()
