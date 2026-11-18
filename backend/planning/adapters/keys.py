"""Header names, logger names and cache keys shared by the provider adapters."""

from planning.domain.values import Coordinate
from shared.weather_variables import WeatherVariable

RETRY_AFTER_HEADER = "Retry-After"
TRANSPORT_LOGGER_NAME = "httpx"

FORECAST_CACHE_PREFIX = "forecast"
FORECAST_CACHE_KEY_SEPARATOR = ":"
FORECAST_CACHE_VARIABLE_SEPARATOR = "+"
FORECAST_CACHE_CELL_DECIMALS = 4


def forecast_cache_key(
    schema_version: int, cell: Coordinate, variables: frozenset[WeatherVariable]
) -> str:
    """The cache key of one cell's forecast for one set of variables."""
    variable_part = FORECAST_CACHE_VARIABLE_SEPARATOR.join(
        sorted(variable.value for variable in variables)
    )
    cell_part = (
        f"{cell.latitude:.{FORECAST_CACHE_CELL_DECIMALS}f},"
        f"{cell.longitude:.{FORECAST_CACHE_CELL_DECIMALS}f}"
    )
    return FORECAST_CACHE_KEY_SEPARATOR.join(
        (FORECAST_CACHE_PREFIX, f"v{schema_version}", cell_part, variable_part)
    )
