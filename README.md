# 🌫️ India Air Quality Pipeline

> An automated, hourly data pipeline that tracks air pollution across **20 Indian cities**, calculates the **official Indian AQI (CPCB)**, detects pollution spikes, checks its own data quality, and measures how accurate air-quality **forecasts** really are. Runs free in the cloud on **GitHub Actions + Neon Postgres**, with a **Streamlit** dashboard.

![CI](https://github.com/Lokesh4561/india-air-quality-pipeline/actions/workflows/ci.yml/badge.svg)
![Pipeline](https://github.com/Lokesh4561/india-air-quality-pipeline/actions/workflows/pipeline.yml/badge.svg)

## Architecture

```
 Open-Meteo Air Quality API  (PM2.5, PM10, NO2, O3, SO2, CO, hourly + 5-day forecast)
            │  every hour (GitHub Actions cron), retry with backoff
            ▼
 ┌─────────────────────────── Neon Postgres  (schema: aq) ───────────────────────────┐
 │ BRONZE  raw_responses   raw JSON exactly as received (replayable)                │
 │ SILVER  readings        1 row per city per hour   (idempotent upsert)            │
 │         forecasts       versioned by issue date   (to score accuracy later)      │
 │ GOLD    aqi_hourly      24h rolling averages → Indian AQI + category + pollutant │
 │         alerts          unhealthy AQI, PM2.5 spikes (z-score), deduped per day   │
 │         dq_results      freshness, completeness, validity, null-rate checks      │
 └───────────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
 Streamlit dashboard: map, city ranking, history charts, alerts, data quality
```

## What makes it interesting

| Feature | Detail |
|---|---|
| **Indian AQI (CPCB)** | Sub-indices from PM2.5/PM10 24-hour averages using official breakpoints; needs ≥16 of 24 hours, like CPCB. Unit-tested at every breakpoint. |
| **Medallion layers** | Bronze (raw JSON) → Silver (clean hourly rows) → Gold (AQI, alerts) |
| **Idempotent** | Upserts on natural keys, so re-running any hour never duplicates data |
| **Spike detection** | Latest PM2.5 vs the city's own 7-day baseline (z-score > 3) |
| **Data quality gates** | 5 automated checks every run; the scheduled run fails (and emails you) if data goes stale or bad |
| **Forecast accuracy** | Stores every forecast, then scores it against what actually happened (MAE by lead time) |
| **Serverless & free** | GitHub Actions runs it hourly even when your laptop is off |

## Results

| Metric | Value |
|---|---|
| Cities tracked | 20 |
| Hourly readings stored | _fill in_ |
| Forecast MAE, 1 day ahead (PM2.5) | _fill in_ µg/m³ |
| Forecast MAE, 3 days ahead (PM2.5) | _fill in_ µg/m³ |

---

# Step-by-step build guide

Do the steps in order. Paste **one command at a time** and wait for it to finish before the next one.

## Step 1: Put the project on your laptop and GitHub

1. Unzip `india-air-quality-pipeline.zip`: right-click it → **Extract All** → **Extract**.
2. Open the folder that contains `README.md`. Click the File Explorer address bar, type `code .` and press **Enter**. VS Code opens.
3. In VS Code, press **Ctrl + `** to open the terminal. Check you're in the right folder with `dir`: you should see `README.md`.
4. On GitHub, create a new **Public** repo named `india-air-quality-pipeline`, **without** a README.
5. In the terminal:
   ```
   git init
   git add .
   git commit -m "chore: project scaffold"
   git branch -M main
   git remote add origin https://github.com/Lokesh4561/india-air-quality-pipeline.git
   git push -u origin main
   ```

## Step 2: Install the packages
```
pip install -r requirements-dev.txt
pytest -q
```
✅ You should see **`25 passed`**.

## Step 3: Connect your Neon database
You can reuse your existing Neon database. This project keeps its tables in a separate `aq` schema, so it won't touch your DocQA tables.

Replace `PASTE_NEON_LINK_HERE` with your Neon link, keeping the quotes:
```
Set-Content -Path .env -Encoding ascii -Value "DATABASE_URL=PASTE_NEON_LINK_HERE"
```
Check it:
```
python -m aq.db
```
✅ You should see **`Database initialised (schema 'aq').`**

## Step 4: First run, loading 3 months of history
```
python -m aq.pipeline --backfill-days 92
```
✅ About 1–2 minutes. You'll see 20 cities loaded, AQI rows created, any alerts, and 5 data quality checks.

Run it **again** with `python -m aq.pipeline`. Nothing is duplicated, which proves idempotency.

## Step 5: Open the dashboard
```
streamlit run dashboard/app.py
```
✅ Your browser opens a dashboard with the AQI map, city ranking, history charts, alerts and data quality. Take a **screenshot** for this README (save it as `docs/dashboard.png`).

Press **Ctrl + C** in the terminal to stop it.

📝 Commit: `git add .` → `git commit -m "feat: first full pipeline run and dashboard"` → `git push`

## Step 6: Make it run every hour in the cloud ⭐
1. On GitHub, open your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
   - **Name:** `DATABASE_URL`
   - **Secret:** your Neon link
   - Click **Add secret**
2. Go to the **Actions** tab → click **"Hourly air quality pipeline"** → **Run workflow** → **Run workflow**.
3. After about 1 minute it should show a green ✅. From now on it runs **every hour automatically**, even when your laptop is off.

> GitHub pauses scheduled workflows after 60 days with no commits. Push a small change at least once every two months.

## Step 7: Measure forecast accuracy (after 3–4 days of hourly runs)
```
python -m aq.forecast_eval
```
It prints the forecast error (MAE) for 1, 2, 3… days ahead. Put the numbers in the **Results** table above.

## Step 8: Make it yours (pick 2 or more) 💡
These are what make the project truly yours, and they give you the best interview stories:
- [ ] **Deploy the dashboard for free** on [Streamlit Community Cloud](https://streamlit.io/cloud). Add `DATABASE_URL` as a secret there, then put the live link at the top of this README.
- [ ] **Telegram or email alerts:** send new alerts to your phone from `aq/alerts.py`.
- [ ] **Add NO₂, O₃ and SO₂** to the AQI using the CPCB breakpoints. Write the tests first, in `tests/test_aqi.py`.
- [ ] **Your own forecast model:** predict tomorrow's PM2.5 (for example with a moving average or linear regression on the last 7 days), and compare its MAE with Open-Meteo's forecast.
- [ ] **Compare with real ground stations:** add OpenAQ station measurements and compare them with the modelled values.
- [ ] **Add more cities:** edit `aq/cities.py`.

## Resume bullet (after Step 7)

> **India Air Quality Pipeline** | Python, PostgreSQL (Neon), GitHub Actions, Streamlit
> - Built an hourly, serverless pipeline tracking **20 Indian cities** (bronze → silver → gold), computing the official **CPCB AQI** from 24-hour PM averages, with idempotent upserts and retry/backoff.
> - Added automated data quality gates (freshness, completeness, validity, null-rate), z-score spike alerts, and a forecast-accuracy evaluation (**MAE X µg/m³** at 1 day ahead), visualised in a Streamlit dashboard.

## Project structure
```
aq/
  cities.py         20 cities and their coordinates
  config.py         settings and thresholds
  aqi.py            Indian AQI (CPCB) calculation, pure and unit-tested
  db.py             schema (aq.*) and connection with retry
  ingest.py         API → bronze → silver (idempotent)
  transform.py      24h rolling averages → AQI (gold)
  alerts.py         unhealthy AQI and PM2.5 spike alerts
  quality.py        data quality checks
  forecast_eval.py  forecast accuracy (MAE by lead time)
  pipeline.py       runs everything in order
dashboard/app.py    Streamlit dashboard
tests/              unit tests (AQI, parsing, rolling averages)
.github/workflows/  CI (tests) and the hourly pipeline
```

## Notes and honest limitations
- **Data source:** [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api), modelled data from the Copernicus Atmosphere Monitoring Service (CAMS), not ground-station measurements. It's free and needs no API key.
- **AQI simplification:** the official CPCB AQI uses at least 3 pollutants including PM2.5 or PM10. This version uses PM2.5 and PM10, which dominate the AQI in most Indian cities. Adding more pollutants is one of the Step 8 improvements.

## Author
**Lokesh Reddy Maddali**, Data Engineer · [GitHub](https://github.com/Lokesh4561) · [LinkedIn](https://www.linkedin.com/in/lokesh-reddy-maddali-455815446/)
