"""Which forecast cell and hour a position and time read (`docs/trip-planning.md`, Weather lookup).

An hourly sum over the preceding hour is the rate per hour, so it is read as is.
"""

import math
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from types import MappingProxyType

from planning.domain.risk_constants import CELL_KEY_DECIMALS, FORECAST_STEP, HALF_STEP
from planning.domain.values import CellForecast, Coordinate
from shared.weather_variables import WEATHER_VARIABLES, Aggregation, WeatherVariable


def _snap(degrees: float, cell_size_deg: float) -> float:
    snapped = math.floor(degrees / cell_size_deg + HALF_STEP) * cell_size_deg
    return round(snapped, CELL_KEY_DECIMALS) + 0.0


def cell_key(coordinate: Coordinate, cell_size_deg: float) -> Coordinate:
    """The center of the grid cell holding the coordinate.

    Each degree value is rounded to the nearest multiple of `cell_size_deg` (halves go up), then
    to `CELL_KEY_DECIMALS` decimals, so the same cell always gives an equal key.
    """
    return Coordinate(
        latitude=_snap(coordinate.latitude, cell_size_deg),
        longitude=_snap(coordinate.longitude, cell_size_deg),
    )


def _nearest_hour(offset_hours: float) -> int:
    return math.floor(offset_hours + HALF_STEP)


def _first_hour_at_or_after(offset_hours: float) -> int:
    return math.ceil(offset_hours)


HOUR_CHOICE: Mapping[Aggregation, Callable[[float], int]] = MappingProxyType(
    {
        Aggregation.INSTANT: _nearest_hour,
        Aggregation.PRECEDING_HOUR_SUM: _first_hour_at_or_after,
    },
)


def hour_index(
    forecast: CellForecast, arrival_utc: datetime, aggregation: Aggregation
) -> int | None:
    """Index into `forecast.hours_utc` of the hour to read for the arrival time.

    INSTANT reads the nearest hour (half past reads the later hour); PRECEDING_HOUR_SUM reads the
    first hour at or after the arrival. None when that hour is not in the forecast.
    """
    if not forecast.hours_utc:
        return None
    offset_hours = (arrival_utc - forecast.hours_utc[0]) / FORECAST_STEP
    index = HOUR_CHOICE[aggregation](offset_hours)
    if index < 0 or index >= len(forecast.hours_utc):
        return None
    return index


def value_at(
    forecast: CellForecast, arrival_utc: datetime, variable: WeatherVariable
) -> float | None:
    """The variable's metric value for the arrival time; None outside the forecast or missing."""
    index = hour_index(forecast, arrival_utc, WEATHER_VARIABLES[variable].aggregation)
    series = forecast.values.get(variable)
    if index is None or series is None or index >= len(series):
        return None
    return series[index]


def values_at(
    forecast: CellForecast, arrival_utc: datetime, variables: Iterable[WeatherVariable]
) -> Mapping[WeatherVariable, float | None]:
    """Every requested variable's metric value for the arrival time (see `value_at`)."""
    return {variable: value_at(forecast, arrival_utc, variable) for variable in variables}
