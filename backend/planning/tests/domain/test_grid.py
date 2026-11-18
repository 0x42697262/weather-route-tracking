import time
from datetime import UTC, datetime, timedelta

from planning.domain.grid import build_grid, grid_hours
from planning.domain.risk import classify, rule_set_variables
from planning.domain.risk_constants import FORECAST_WINDOW_HOURS
from planning.domain.values import CellForecast, Coordinate
from planning.domain.weather_lookup import values_at
from rulesets.domain.defaults import default_rule_set_document
from rulesets.domain.validator import validate_rule_set
from shared.risk_levels import RiskLevel
from shared.units import Unit, convert
from shared.weather_variables import WeatherVariable

RULES = validate_rule_set(default_rule_set_document())
WIND = WeatherVariable.WIND_SPEED
RAIN = WeatherVariable.RAIN_RATE
SNOW = WeatherVariable.SNOWFALL_RATE
START = datetime(2026, 11, 20, 0, tzinfo=UTC)
FORECAST_HOURS = 72
DEPARTURE = START + timedelta(hours=2, minutes=10)
LOAD_KG = convert(40001, Unit.POUNDS, Unit.KILOGRAMS)


def _forecast(cell: Coordinate, hours: int = FORECAST_HOURS) -> CellForecast:
    hours_utc = tuple(START + timedelta(hours=index) for index in range(hours))
    wind_kmh = convert(38, Unit.MILES_PER_HOUR, Unit.KILOMETERS_PER_HOUR)
    return CellForecast(
        cell=cell,
        hours_utc=hours_utc,
        values={
            WIND: tuple(wind_kmh if index % 2 else 0.0 for index in range(hours)),
            RAIN: tuple(float(index % 5) for index in range(hours)),
            SNOW: tuple(0.0 for _ in range(hours)),
        },
    )


def test_grid_hours_cover_the_window() -> None:
    hours = grid_hours(DEPARTURE, FORECAST_WINDOW_HOURS)

    assert len(hours) == FORECAST_WINDOW_HOURS + 1
    assert hours[0] == DEPARTURE
    assert hours[-1] == DEPARTURE + timedelta(hours=FORECAST_WINDOW_HOURS)


def test_grid_matches_the_checkpoint_classifier() -> None:
    forecast = _forecast(Coordinate(35.5, -97.5))

    grid = build_grid((forecast,), DEPARTURE, LOAD_KG, RULES)

    cell = grid.cells[0]
    assert cell.center == forecast.cell
    assert grid.variables == (WIND, RAIN, SNOW)
    assert [series.variable for series in cell.conditions] == list(grid.variables)
    for index, moment in enumerate(grid.hours_utc):
        expected = classify(values_at(forecast, moment, rule_set_variables(RULES)), LOAD_KG, RULES)
        assert cell.combined[index] is expected.level
        for series, condition in zip(cell.conditions, expected.conditions, strict=True):
            assert series.values[index] == condition.value
            assert series.levels[index] is condition.level


def test_wind_condition_level_includes_its_load_rule() -> None:
    grid = build_grid((_forecast(Coordinate(0, 0)),), START, LOAD_KG, RULES, window_hours=1)

    wind = grid.cells[0].conditions[0]
    assert wind.levels == (RiskLevel.LOW, RiskLevel.SEVERE)


def test_hours_without_forecast_are_none() -> None:
    short = _forecast(Coordinate(35.5, -97.5), hours=10)

    grid = build_grid((short,), DEPARTURE, LOAD_KG, RULES)

    cell = grid.cells[0]
    assert cell.combined[0] is not None
    assert all(level is None for level in cell.combined[9:])
    assert all(value is None for series in cell.conditions for value in series.values[9:])
    assert all(level is None for series in cell.conditions for level in series.levels[9:])


def test_300_cells_over_49_hours_is_fast() -> None:
    forecasts = tuple(_forecast(Coordinate(30 + index * 0.1, -97.5)) for index in range(300))

    started = time.perf_counter()
    grid = build_grid(forecasts, DEPARTURE, LOAD_KG, RULES)
    elapsed_s = time.perf_counter() - started

    assert len(grid.cells) == 300
    assert all(len(cell.combined) == FORECAST_WINDOW_HOURS + 1 for cell in grid.cells)
    assert elapsed_s < 5
