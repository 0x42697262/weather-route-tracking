"""Paths, parameter names, headers and the variable table of the Open-Meteo forecast API."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from shared.units import Unit
from shared.weather_variables import WeatherVariable

FORECAST_PATH = "/v1/forecast"

PARAM_LATITUDE = "latitude"
PARAM_LONGITUDE = "longitude"
PARAM_HOURLY = "hourly"
PARAM_FORECAST_DAYS = "forecast_days"
PARAM_TIMEFORMAT = "timeformat"
PARAM_TIMEZONE = "timezone"
PARAM_API_KEY = "apikey"

TIMEFORMAT_UNIXTIME = "unixtime"
TIMEZONE_GMT = "GMT"
LIST_SEPARATOR = ","
TIME_FIELD = "time"

HEADER_RATE_LIMIT_REMAINING = "X-RateLimit-Remaining"
HEADER_RATE_LIMIT_RESET = "X-RateLimit-Reset"

OPERATION_FORECAST = "forecast"


@dataclass(frozen=True, slots=True)
class HourlyField:
    """One hourly field of the API and the unit label the response must carry for it."""

    name: str
    unit_label: str


@dataclass(frozen=True, slots=True)
class VariableSource:
    """How a weather variable is built: the sum of `fields`, each an hourly rate in `unit`."""

    fields: tuple[HourlyField, ...]
    unit: Unit


WIND_SPEED_10M = HourlyField(name="wind_speed_10m", unit_label="km/h")
RAIN = HourlyField(name="rain", unit_label="mm")
SHOWERS = HourlyField(name="showers", unit_label="mm")
SNOWFALL = HourlyField(name="snowfall", unit_label="cm")

VARIABLE_SOURCES: Mapping[WeatherVariable, VariableSource] = MappingProxyType(
    {
        WeatherVariable.WIND_SPEED: VariableSource(
            fields=(WIND_SPEED_10M,), unit=Unit.KILOMETERS_PER_HOUR
        ),
        WeatherVariable.RAIN_RATE: VariableSource(
            fields=(RAIN, SHOWERS), unit=Unit.MILLIMETERS_PER_HOUR
        ),
        WeatherVariable.SNOWFALL_RATE: VariableSource(
            fields=(SNOWFALL,), unit=Unit.CENTIMETERS_PER_HOUR
        ),
    },
)
