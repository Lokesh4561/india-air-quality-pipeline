"""Database connection (with retry for serverless Postgres) and schema.

All tables live in their own `aq` schema, so this project can share a database
(for example your Neon database) with other projects without clashing.
"""

import time

import psycopg

from aq.config import DATABASE_URL

SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS aq;

-- Bronze: raw API responses, kept exactly as received (replayable)
CREATE TABLE IF NOT EXISTS aq.raw_responses (
    id          BIGSERIAL PRIMARY KEY,
    city        TEXT NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    params      JSONB NOT NULL,
    payload     JSONB NOT NULL
);

-- Silver: one clean row per city per hour (observed values)
CREATE TABLE IF NOT EXISTS aq.readings (
    city              TEXT NOT NULL,
    ts                TIMESTAMPTZ NOT NULL,
    pm2_5             DOUBLE PRECISION,
    pm10              DOUBLE PRECISION,
    nitrogen_dioxide  DOUBLE PRECISION,
    ozone             DOUBLE PRECISION,
    sulphur_dioxide   DOUBLE PRECISION,
    carbon_monoxide   DOUBLE PRECISION,
    ingested_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (city, ts)
);

-- Silver: forecasts, versioned by the day they were issued (to measure accuracy later)
CREATE TABLE IF NOT EXISTS aq.forecasts (
    city          TEXT NOT NULL,
    ts            TIMESTAMPTZ NOT NULL,
    issued_date   DATE NOT NULL,
    pm2_5         DOUBLE PRECISION,
    pm10          DOUBLE PRECISION,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (city, ts, issued_date)
);

-- Gold: hourly Indian AQI per city, from 24-hour rolling averages
CREATE TABLE IF NOT EXISTS aq.aqi_hourly (
    city        TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    pm2_5_24h   DOUBLE PRECISION,
    pm10_24h    DOUBLE PRECISION,
    aqi         INT,
    category    TEXT,
    dominant    TEXT,
    PRIMARY KEY (city, ts)
);

-- Gold: alerts (at most one of each type per city per day)
CREATE TABLE IF NOT EXISTS aq.alerts (
    id          BIGSERIAL PRIMARY KEY,
    city        TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    alert_day   DATE NOT NULL,
    alert_type  TEXT NOT NULL,
    value       DOUBLE PRECISION,
    message     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (city, alert_type, alert_day)
);

-- Data quality results for every pipeline run
CREATE TABLE IF NOT EXISTS aq.dq_results (
    id          BIGSERIAL PRIMARY KEY,
    run_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    check_name  TEXT NOT NULL,
    status      TEXT NOT NULL,
    detail      TEXT
);
"""


def get_conn(retries: int = 3) -> psycopg.Connection:
    """Connect with a timeout, retrying with exponential backoff (Neon may be waking up)."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Add it to your .env file (see .env.example).")
    for attempt in range(1, retries + 1):
        try:
            return psycopg.connect(
                DATABASE_URL, autocommit=True, connect_timeout=10,
                keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
            )
        except psycopg.OperationalError:
            if attempt == retries:
                raise
            wait = 2 ** attempt
            print(f"Database connection failed (attempt {attempt}/{retries}), retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(SCHEMA_SQL)


if __name__ == "__main__":
    init_db()
    print("Database initialised (schema 'aq').")
