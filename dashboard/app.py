"""India Air Quality dashboard.

Run from the project folder:  streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make the `aq` package importable

from aq.cities import CITY_COORDS  # noqa: E402
from aq.db import get_conn  # noqa: E402

st.set_page_config(page_title="India Air Quality", page_icon="🌫️", layout="wide")

CATEGORY_COLORS = {
    "Good": "#009966", "Satisfactory": "#58b453", "Moderate": "#e6c229",
    "Poor": "#f08a24", "Very Poor": "#d7301f", "Severe": "#7e0023",
}


@st.cache_data(ttl=600)
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        cols = [d.name for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


st.title("🌫️ India Air Quality")
st.caption("Hourly pipeline · Indian National AQI (CPCB) from 24-hour PM2.5 / PM10 averages · Data: Open-Meteo")

latest = query("""
    SELECT DISTINCT ON (city) city, ts, aqi, category, dominant, pm2_5_24h, pm10_24h
    FROM aq.aqi_hourly ORDER BY city, ts DESC
""")

if latest.empty:
    st.warning("No data yet. Run the pipeline first:  python -m aq.pipeline --backfill-days 92")
    st.stop()

latest = latest.sort_values("aqi", ascending=False)
updated = pd.to_datetime(latest["ts"].max()).tz_convert("Asia/Kolkata")
st.write(f"Last updated: **{updated:%d %b %Y, %H:%M} IST**")

# --- Headline numbers -------------------------------------------------------
worst, best = latest.iloc[0], latest.iloc[-1]
c1, c2, c3 = st.columns(3)
c1.metric("Most polluted", f"{worst.city}", f"AQI {worst.aqi} · {worst.category}", delta_color="off")
c2.metric("Cleanest air", f"{best.city}", f"AQI {best.aqi} · {best.category}", delta_color="off")
c3.metric("Cities Poor or worse", int(latest["category"].isin(["Poor", "Very Poor", "Severe"]).sum()),
          f"of {len(latest)} tracked", delta_color="off")

# --- Map + ranking --------------------------------------------------------------
left, right = st.columns([3, 2])
with left:
    st.subheader("Current AQI by city")
    map_df = latest.assign(
        lat=latest["city"].map(lambda c: CITY_COORDS[c][0]),
        lon=latest["city"].map(lambda c: CITY_COORDS[c][1]),
        color=latest["category"].map(CATEGORY_COLORS),
        size=latest["aqi"].clip(lower=50) * 120,
    )
    st.map(map_df, latitude="lat", longitude="lon", color="color", size="size")
with right:
    st.subheader("Ranking")
    table = latest[["city", "aqi", "category", "dominant", "pm2_5_24h", "pm10_24h"]].rename(columns={
        "city": "City", "aqi": "AQI", "category": "Category", "dominant": "Main pollutant",
        "pm2_5_24h": "PM2.5 (24h)", "pm10_24h": "PM10 (24h)",
    })
    st.dataframe(table, hide_index=True, width="stretch")

# --- City history ------------------------------------------------------------------
st.subheader("City history")
city = st.selectbox("Choose a city", sorted(latest["city"]))
days = st.slider("Days of history", 2, 92, 14)

history = query(
    "SELECT ts, aqi FROM aq.aqi_hourly WHERE city = %s AND ts >= now() - make_interval(days => %s) ORDER BY ts",
    (city, days),
)
readings = query(
    "SELECT ts, pm2_5, pm10 FROM aq.readings WHERE city = %s AND ts >= now() - make_interval(days => %s) ORDER BY ts",
    (city, days),
)
h1, h2 = st.columns(2)
with h1:
    st.caption("AQI (24-hour rolling)")
    st.line_chart(history.set_index("ts")["aqi"])
with h2:
    st.caption("Hourly PM2.5 and PM10 (µg/m³)")
    st.line_chart(readings.set_index("ts")[["pm2_5", "pm10"]])

# --- Alerts and data quality ---------------------------------------------------------
a, q = st.columns(2)
with a:
    st.subheader("Recent alerts")
    alerts = query("SELECT created_at, city, alert_type, message FROM aq.alerts ORDER BY created_at DESC LIMIT 20")
    st.dataframe(alerts, hide_index=True, width="stretch") if not alerts.empty else st.info("No alerts yet.")
with q:
    st.subheader("Latest data quality checks")
    dq = query("""
        SELECT DISTINCT ON (check_name) check_name, status, detail, run_at
        FROM aq.dq_results ORDER BY check_name, run_at DESC
    """)
    st.dataframe(dq, hide_index=True, width="stretch")
