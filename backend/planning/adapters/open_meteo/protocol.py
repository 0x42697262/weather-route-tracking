"""Pure request building and response parsing for the Open-Meteo forecast API.

Responses are hourly sums of the preceding hour for rain, showers and snowfall, and instant
values for wind (`docs/facts.md` F-26, F-27); a sum over one hour is the rate per hour.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from itertools import pairwise

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from planning.adapters.open_meteo.constants import (
    FORECAST_DAYS,
    HOUR_S,
    REQUEST_COORDINATE_DECIMALS,
)
from planning.adapters.open_meteo.keys import (
    LIST_SEPARATOR,
    PARAM_API_KEY,
    PARAM_FORECAST_DAYS,
    PARAM_HOURLY,
    PARAM_LATITUDE,
    PARAM_LONGITUDE,
    PARAM_TIMEFORMAT,
    PARAM_TIMEZONE,
    TIME_FIELD,
    TIMEFORMAT_UNIXTIME,
    TIMEZONE_GMT,
    VARIABLE_SOURCES,
    VariableSource,
)
from planning.domain.values import CellForecast, Coordinate
from planning.errors import UpstreamInvalidResponse
from shared.units import convert, round_measure
from shared.weather_variables import WEATHER_VARIABLES, WeatherVariable

type QueryParams = list[tuple[str, str | int | float | bool | None]]
type Series = tuple[float | None, ...]


class _Location(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    hourly_units: dict[str, str]
    hourly: dict[str, Series]


_LOCATIONS = TypeAdapter(tuple[_Location, ...])


def hourly_fields(variables: frozenset[WeatherVariable]) -> tuple[str, ...]:
    """The hourly fields the variables need, each once, in a stable order."""
    names = {field.name for variable in variables for field in VARIABLE_SOURCES[variable].fields}
    return tuple(sorted(names))


def _coordinates(values: Sequence[float]) -> str:
    return LIST_SEPARATOR.join(f"{value:.{REQUEST_COORDINATE_DECIMALS}f}" for value in values)


def forecast_query(
    cells: Sequence[Coordinate], variables: frozenset[WeatherVariable], api_key: str | None
) -> QueryParams:
    """The forecast query for several cells: only the needed fields, unix times in GMT."""
    params: QueryParams = [
        (PARAM_LATITUDE, _coordinates([cell.latitude for cell in cells])),
        (PARAM_LONGITUDE, _coordinates([cell.longitude for cell in cells])),
        (PARAM_HOURLY, LIST_SEPARATOR.join(hourly_fields(variables))),
        (PARAM_FORECAST_DAYS, str(FORECAST_DAYS)),
        (PARAM_TIMEFORMAT, TIMEFORMAT_UNIXTIME),
        (PARAM_TIMEZONE, TIMEZONE_GMT),
    ]
    if api_key:
        params.append((PARAM_API_KEY, api_key))
    return params


def _invalid() -> UpstreamInvalidResponse:
    return UpstreamInvalidResponse()


def _hours(location: _Location) -> tuple[datetime, ...]:
    if location.hourly_units.get(TIME_FIELD) != TIMEFORMAT_UNIXTIME:
        raise _invalid()
    times = location.hourly.get(TIME_FIELD)
    if not times:
        raise _invalid()
    seconds: list[int] = []
    for value in times:
        if value is None or not value.is_integer() or int(value) % HOUR_S:
            raise _invalid()
        seconds.append(int(value))
    if any(later - earlier != HOUR_S for earlier, later in pairwise(seconds)):
        raise _invalid()
    return tuple(datetime.fromtimestamp(value, UTC) for value in seconds)


def _sum(values: tuple[float | None, ...]) -> float | None:
    total = 0.0
    for value in values:
        if value is None:
            return None
        total += value
    return round_measure(total)


def _variable_series(location: _Location, variable: WeatherVariable, hour_count: int) -> Series:
    source: VariableSource = VARIABLE_SOURCES[variable]
    series: list[Series] = []
    for field in source.fields:
        values = location.hourly.get(field.name)
        if location.hourly_units.get(field.name) != field.unit_label or values is None:
            raise _invalid()
        if len(values) != hour_count:
            raise _invalid()
        series.append(values)
    metric_unit = WEATHER_VARIABLES[variable].metric_unit
    combined = (_sum(values) for values in zip(*series, strict=True))
    return tuple(
        None if value is None else convert(value, source.unit, metric_unit) for value in combined
    )


def parse_forecasts(
    payload: object, cells: Sequence[Coordinate], variables: frozenset[WeatherVariable]
) -> tuple[CellForecast, ...]:
    """One forecast per requested cell, in request order, keyed by the requested cell.

    A one-location request answers with an object, a several-location request with a list.

    Raises:
        UpstreamInvalidResponse: the body does not match the request.
    """
    items = payload if isinstance(payload, list) else [payload]
    try:
        locations = _LOCATIONS.validate_python(items)
    except ValidationError:
        raise _invalid() from None
    if len(locations) != len(cells):
        raise _invalid()
    forecasts: list[CellForecast] = []
    for cell, location in zip(cells, locations, strict=True):
        hours = _hours(location)
        values = {
            variable: _variable_series(location, variable, len(hours))
            for variable in sorted(variables)
        }
        forecasts.append(CellForecast(cell=cell, hours_utc=hours, values=values))
    return tuple(forecasts)
