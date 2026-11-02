"""Indian National Air Quality Index (CPCB) calculation from PM2.5 and PM10.

Each pollutant's concentration is mapped to a sub-index by linear interpolation
within CPCB breakpoints; the AQI is the highest sub-index, and that pollutant is
the "dominant" one.

Simplification (documented in the README): the official AQI needs 24-hour averages
of at least three pollutants including PM2.5 or PM10. This project uses 24-hour
rolling averages of PM2.5 and PM10, which drive the AQI in most Indian cities.
"""

import math

# (concentration_low, concentration_high, index_low, index_high), in µg/m³
BREAKPOINTS: dict[str, list[tuple[float, float, int, int]]] = {
    "pm2_5": [(0, 30, 0, 50), (30, 60, 50, 100), (60, 90, 100, 200),
              (90, 120, 200, 300), (120, 250, 300, 400), (250, 380, 400, 500)],
    "pm10": [(0, 50, 0, 50), (50, 100, 50, 100), (100, 250, 100, 200),
             (250, 350, 200, 300), (350, 430, 300, 400), (430, 510, 400, 500)],
}

CATEGORIES: list[tuple[int, str]] = [
    (50, "Good"), (100, "Satisfactory"), (200, "Moderate"),
    (300, "Poor"), (400, "Very Poor"), (500, "Severe"),
]
UNHEALTHY = {"Poor", "Very Poor", "Severe"}


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def sub_index(pollutant: str, concentration) -> int | None:
    """Return the CPCB sub-index (0–500) for one pollutant, or None if unknown."""
    if _missing(concentration) or concentration < 0:
        return None
    for c_lo, c_hi, i_lo, i_hi in BREAKPOINTS[pollutant]:
        if concentration <= c_hi:
            return round(i_lo + (i_hi - i_lo) * (concentration - c_lo) / (c_hi - c_lo))
    return 500  # beyond the last breakpoint: capped at the maximum


def category(aqi: int | None) -> str | None:
    if aqi is None:
        return None
    for upper, name in CATEGORIES:
        if aqi <= upper:
            return name
    return "Severe"


def compute_aqi(pm2_5, pm10) -> tuple[int | None, str | None, str | None]:
    """Return (aqi, category, dominant_pollutant) from 24h-average PM2.5 and PM10."""
    subs = {name: idx for name, idx in (("pm2_5", sub_index("pm2_5", pm2_5)),
                                        ("pm10", sub_index("pm10", pm10))) if idx is not None}
    if not subs:
        return None, None, None
    dominant = max(subs, key=subs.get)
    aqi = subs[dominant]
    return aqi, category(aqi), dominant
