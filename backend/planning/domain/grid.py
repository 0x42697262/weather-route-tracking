"""Classify every heatmap cell for every hour of the forecast window (`docs/trip-planning.md`,
Heatmap grid), with the same `classify` as checkpoints."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from planning.domain.risk import Classification, classify, rule_set_variables
from planning.domain.risk_constants import FORECAST_STEP, FORECAST_WINDOW_HOURS
from planning.domain.values import CellForecast, Coordinate
from planning.domain.weather_lookup import values_at
from rulesets.domain.schema import RuleSet
from shared.risk_levels import RiskLevel
from shared.weather_variables import WeatherVariable


@dataclass(frozen=True, slots=True)
class ConditionSeries:
    """One condition in one cell, one entry per hour.

    `values` are metric; `levels` are that condition's own level (its bands raised by load rules
    on its variable). None where there is no forecast.
    """

    variable: WeatherVariable
    values: tuple[float | None, ...]
    levels: tuple[RiskLevel | None, ...]


@dataclass(frozen=True, slots=True)
class GridCell:
    """A cell's center, its conditions in rule set order, and the combined level per hour."""

    center: Coordinate
    conditions: tuple[ConditionSeries, ...]
    combined: tuple[RiskLevel | None, ...]


@dataclass(frozen=True, slots=True)
class HeatmapGrid:
    """Every cell; `hours_utc[index]` is the time of entry `index` in each series."""

    hours_utc: tuple[datetime, ...]
    variables: tuple[WeatherVariable, ...]
    cells: tuple[GridCell, ...]


def grid_hours(departure_utc: datetime, window_hours: int) -> tuple[datetime, ...]:
    """The departure plus 0 to `window_hours` whole hours."""
    return tuple(departure_utc + FORECAST_STEP * hour for hour in range(window_hours + 1))


def _cell(
    forecast: CellForecast,
    hours_utc: tuple[datetime, ...],
    load_kg: float,
    rules: RuleSet,
) -> GridCell:
    variables = rule_set_variables(rules)
    results: list[Classification] = [
        classify(values_at(forecast, moment, variables), load_kg, rules) for moment in hours_utc
    ]
    conditions = tuple(
        ConditionSeries(
            variable=condition.variable,
            values=tuple(result.conditions[index].value for result in results),
            levels=tuple(result.conditions[index].level for result in results),
        )
        for index, condition in enumerate(rules.conditions)
    )
    return GridCell(
        center=forecast.cell,
        conditions=conditions,
        combined=tuple(result.level for result in results),
    )


def build_grid(
    forecasts: Sequence[CellForecast],
    departure_utc: datetime,
    load_kg: float,
    rules: RuleSet,
    window_hours: int = FORECAST_WINDOW_HOURS,
) -> HeatmapGrid:
    """Classify each cell at the departure and every whole hour after it up to `window_hours`.

    Hours outside a cell's forecast give None values and an Unknown level.
    """
    hours_utc = grid_hours(departure_utc, window_hours)
    return HeatmapGrid(
        hours_utc=hours_utc,
        variables=tuple(condition.variable for condition in rules.conditions),
        cells=tuple(_cell(forecast, hours_utc, load_kg, rules) for forecast in forecasts),
    )
