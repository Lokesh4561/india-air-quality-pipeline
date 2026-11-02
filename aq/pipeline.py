"""Run the full pipeline: ingest -> transform (AQI) -> alerts -> data quality.

Examples:
  python -m aq.pipeline                    # normal hourly run (last 1 day + 2-day forecast)
  python -m aq.pipeline --backfill-days 92 # first run: load ~3 months of history
  python -m aq.pipeline --strict           # exit with an error if any data quality check fails
"""

import argparse
import sys
import time

from aq import alerts, ingest, quality, transform
from aq.db import get_conn, init_db


def step(name: str):
    print(f"\n== {name} ==")
    return time.time()


def main() -> int:
    parser = argparse.ArgumentParser(description="India air quality pipeline")
    parser.add_argument("--backfill-days", type=int, default=1, help="days of history to (re)load, max 92")
    parser.add_argument("--forecast-days", type=int, default=2, help="days of forecast to store, max 7")
    parser.add_argument("--strict", action="store_true", help="fail the run if a data quality check fails")
    args = parser.parse_args()

    started = time.time()
    init_db()

    with get_conn() as conn:
        t = step("1. Ingest (bronze + silver)")
        counts = ingest.run(conn, past_days=min(args.backfill_days, 92), forecast_days=min(args.forecast_days, 7))
        print(f"  -> {counts} in {time.time() - t:.1f}s")

        t = step("2. Transform: 24h averages -> Indian AQI (gold)")
        n = transform.run(conn, days=max(args.backfill_days, 2))
        print(f"  -> {n} AQI rows upserted in {time.time() - t:.1f}s")

        step("3. Alerts")
        new_alerts = alerts.run(conn)
        for city, alert_type, message in new_alerts:
            print(f"  ALERT [{alert_type}] {message}")
        if not new_alerts:
            print("  no new alerts")

        step("4. Data quality checks")
        results = quality.run(conn)
        for name, status, detail in results:
            print(f"  {status:<4} {name:<13} {detail}")

    failed = [r for r in results if r[1] == "FAIL"] + ([("ingest", "FAIL", "")] if counts["failed"] else [])
    print(f"\nPipeline finished in {time.time() - started:.1f}s with {len(failed)} failed check(s).")
    return 1 if (args.strict and failed) else 0


if __name__ == "__main__":
    sys.exit(main())
