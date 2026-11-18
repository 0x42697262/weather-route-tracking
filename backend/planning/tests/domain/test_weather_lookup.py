from datetime import UTC, datetime, timedelta

import pytest

from planning.domain.values import CellForecast, Coordinate
from planning.domain.weather_lookup import cell_key, hour_index, value_at, values_at
from shared.weather_variables import Aggregation, WeatherVariable

WIND = WeatherVariable.WIND_SPEED
RAIN = WeatherVariable.RAIN_RATE
SNOW = WeatherVariable.SNOWFALL_RATE
START = datetime(2026, 11, 20, 6, tzinfo=UTC)
HOURS = tuple(START + timedelta(hours=index) for index in range(4))
FORECAST = CellForecast(
    cell=Coordinate(35.5, -97.5),
    hours_utc=HOURS,
    values={
        WIND: (10.0, 20.0, 30.0, 40.0),
        RAIN: (0.0, 1.0, None, 3.0),
    },
)


def _at(minutes: float) -> datetime:
    return START + timedelta(minutes=minutes)


@pytest.mark.parametrize(
    ("minutes", "instant", "preceding_sum"),
    [
        (0, 0, 0),
        (60, 1, 1),
        (180, 3, 3),
        (20, 0, 1),
        (29, 0, 1),
        (30, 1, 1),
        (31, 1, 1),
        (90, 2, 2),
        (150, 3, 3),
        (-20, 0, 0),
        (-30, 0, 0),
        (-31, None, 0),
        (-59, None, 0),
        (-60, None, None),
        (-61, None, None),
        (200, 3, None),
        (209, 3, None),
        (210, None, None),
        (181, 3, None),
    ],
)
def test_hour_index_by_aggregation(
    minutes: float, instant: int | None, preceding_sum: int | None
) -> None:
    assert hour_index(FORECAST, _at(minutes), Aggregation.INSTANT) == instant
    assert hour_index(FORECAST, _at(minutes), Aggregation.PRECEDING_HOUR_SUM) == preceding_sum


def test_values_at_exact_hour() -> None:
    assert values_at(FORECAST, _at(60), (WIND, RAIN)) == {WIND: 20.0, RAIN: 1.0}


def test_values_at_half_past_reads_later_hour_for_both() -> None:
    assert values_at(FORECAST, _at(30), (WIND, RAIN)) == {WIND: 20.0, RAIN: 1.0}


def test_values_at_twenty_past_reads_nearest_and_next_hour() -> None:
    assert values_at(FORECAST, _at(80), (WIND, RAIN)) == {WIND: 20.0, RAIN: None}


def test_before_first_hour_is_missing() -> None:
    assert values_at(FORECAST, _at(-120), (WIND, RAIN)) == {WIND: None, RAIN: None}


def test_after_last_hour_is_missing() -> None:
    assert values_at(FORECAST, _at(240), (WIND, RAIN)) == {WIND: None, RAIN: None}


def test_variable_not_in_forecast_is_missing() -> None:
    assert value_at(FORECAST, _at(0), SNOW) is None


def test_empty_forecast_is_missing() -> None:
    empty = CellForecast(cell=Coordinate(0, 0), hours_utc=(), values={})

    assert value_at(empty, _at(0), WIND) is None


@pytest.mark.parametrize(
    ("latitude", "longitude", "size_deg", "expected"),
    [
        (35.47, -97.52, 0.1, Coordinate(35.5, -97.5)),
        (35.44, -97.56, 0.1, Coordinate(35.4, -97.6)),
        (0.04, -0.04, 0.1, Coordinate(0.0, 0.0)),
        (35.47, -97.52, 0.25, Coordinate(35.5, -97.5)),
        (35.12, -97.13, 0.25, Coordinate(35.0, -97.25)),
    ],
)
def test_cell_key_rounds_to_the_grid(
    latitude: float, longitude: float, size_deg: float, expected: Coordinate
) -> None:
    assert cell_key(Coordinate(latitude, longitude), size_deg) == expected


def test_cell_key_is_stable_inside_a_cell() -> None:
    keys = {
        cell_key(Coordinate(35.46 + step * 0.001, -97.54 + step * 0.001), 0.1) for step in range(80)
    }

    assert keys == {Coordinate(35.5, -97.5)}


def test_cell_key_has_no_negative_zero() -> None:
    key = cell_key(Coordinate(-0.01, -0.01), 0.1)

    assert str(key.latitude) == "0.0"
    assert str(key.longitude) == "0.0"
