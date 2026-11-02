"""Data quality checks, run after every load. Results are stored in aq.dq_results."""

from aq.cities import CITIES
from aq.config import FRESHNESS_HOURS, MAX_NULL_RATE, MAX_VALID_CONCENTRATION, MIN_ROWS_PER_DAY

CHECKS = {
    "freshness": (
        "SELECT count(*) FROM (SELECT city, max(ts) AS latest FROM aq.readings GROUP BY city) t "
        "WHERE latest < now() - make_interval(hours => %(hours)s)",
        "cities with stale data (older than {hours}h)",
    ),
    "completeness": (
        "SELECT count(*) FROM (SELECT city, count(*) AS n FROM aq.readings "
        "WHERE ts >= now() - interval '24 hours' GROUP BY city) t WHERE n < %(min_rows)s",
        "cities with fewer than {min_rows} hourly rows in the last 24h",
    ),
    "validity": (
        "SELECT count(*) FROM aq.readings WHERE ts >= now() - interval '24 hours' AND ("
        "pm2_5 < 0 OR pm10 < 0 OR pm2_5 > %(max_val)s OR pm10 > %(max_val)s)",
        "readings in the last 24h with negative or impossible PM values",
    ),
    "null_rate": (
        "SELECT count(*) FROM (SELECT city, avg((pm2_5 IS NULL)::int) AS null_rate FROM aq.readings "
        "WHERE ts >= now() - interval '24 hours' GROUP BY city) t WHERE null_rate > %(max_null)s",
        "cities with more than {max_null:.0%} missing PM2.5 values in the last 24h",
    ),
}


def run(conn) -> list[tuple[str, str, str]]:
    """Run every check; returns (check_name, PASS/FAIL, detail)."""
    params = {
        "hours": FRESHNESS_HOURS,
        "min_rows": MIN_ROWS_PER_DAY,
        "max_val": MAX_VALID_CONCENTRATION,
        "max_null": MAX_NULL_RATE,
    }
    results = []

    tracked = conn.execute("SELECT count(DISTINCT city) FROM aq.readings").fetchone()[0]
    missing = len(CITIES) - tracked
    results.append(("coverage", "PASS" if missing <= 0 else "FAIL",
                    f"{tracked}/{len(CITIES)} cities have data"))

    for name, (sql, description) in CHECKS.items():
        bad = conn.execute(sql, params).fetchone()[0]
        results.append((name, "PASS" if bad == 0 else "FAIL", f"{bad} {description.format(**params)}"))

    with conn.cursor() as cur:
        cur.executemany("INSERT INTO aq.dq_results (check_name, status, detail) VALUES (%s, %s, %s)", results)
    return results
