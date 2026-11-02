import math

import pytest

from aq.aqi import category, compute_aqi, sub_index


@pytest.mark.parametrize("conc,expected", [
    (0, 0), (30, 50), (60, 100), (90, 200), (120, 300), (250, 400), (380, 500),
])
def test_pm25_breakpoint_edges(conc, expected):
    assert sub_index("pm2_5", conc) == expected


def test_pm25_interpolates_inside_a_band():
    # 45 is halfway between 30 and 60 -> halfway between 50 and 100
    assert sub_index("pm2_5", 45) == 75


def test_pm10_breakpoints():
    assert sub_index("pm10", 50) == 50
    assert sub_index("pm10", 175) == 150   # halfway in 100-250 -> halfway in 100-200


def test_values_above_scale_are_capped():
    assert sub_index("pm2_5", 999) == 500


@pytest.mark.parametrize("bad", [None, float("nan"), -5])
def test_missing_or_invalid_values(bad):
    assert sub_index("pm2_5", bad) is None


@pytest.mark.parametrize("aqi,name", [
    (0, "Good"), (50, "Good"), (51, "Satisfactory"), (150, "Moderate"),
    (250, "Poor"), (350, "Very Poor"), (450, "Severe"),
])
def test_categories(aqi, name):
    assert category(aqi) == name


def test_aqi_is_the_worst_sub_index():
    # PM2.5 = 45 -> 75, PM10 = 175 -> 150  => AQI 150, dominated by PM10
    assert compute_aqi(45, 175) == (150, "Moderate", "pm10")


def test_aqi_with_one_pollutant_missing():
    assert compute_aqi(None, 50) == (50, "Good", "pm10")
    assert compute_aqi(math.nan, None) == (None, None, None)
