"""Settings, read from environment variables (.env locally, GitHub Secrets in Actions)."""

import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip().strip("\"'")  # ignore stray spaces, line breaks, quotes
API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
POLLUTANTS = ["pm2_5", "pm10", "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide"]
IST = ZoneInfo("Asia/Kolkata")

# Data quality thresholds
FRESHNESS_HOURS = 3        # newest reading per city must be at most this old
MIN_ROWS_PER_DAY = 20      # expected hourly rows per city in the last 24h
MAX_VALID_CONCENTRATION = 2000.0
MAX_NULL_RATE = 0.10

if not DATABASE_URL:  # Streamlit Community Cloud: fall back to st.secrets
    try:
        import streamlit as st

        DATABASE_URL = str(st.secrets.get("DATABASE_URL", "")).strip().strip("\"'")
    except Exception:
        pass
