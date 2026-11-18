"""The weather condition table: which variables exist, their metric unit, the units staff may
enter them in, and how the provider reports each over time."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from shared.units import Dimension, Unit, units_of


class WeatherVariable(StrEnum):
    """Conditions a rule set can rate."""

    WIND_SPEED = "wind_speed"
    RAIN_RATE = "rain_rate"
    SNOWFALL_RATE = "snowfall_rate"


class Aggregation(StrEnum):
    """How a provider reports a variable at an hourly timestamp.

    INSTANT: the value at the timestamp; read the hour nearest the arrival time.
    PRECEDING_HOUR_SUM: the total of the hour before the timestamp; read the first hour at or
    after the arrival time.
    """

    INSTANT = "instant"
    PRECEDING_HOUR_SUM = "preceding_hour_sum"


@dataclass(frozen=True, slots=True)
class VariableInfo:
    """A variable's properties."""

    metric_unit: Unit
    allowed_units: frozenset[Unit]
    aggregation: Aggregation
    text_key: str


WEATHER_VARIABLES: Mapping[WeatherVariable, VariableInfo] = MappingProxyType(
    {
        WeatherVariable.WIND_SPEED: VariableInfo(
            metric_unit=Unit.KILOMETERS_PER_HOUR,
            allowed_units=units_of(Dimension.SPEED),
            aggregation=Aggregation.INSTANT,
            text_key="wind_speed",
        ),
        WeatherVariable.RAIN_RATE: VariableInfo(
            metric_unit=Unit.MILLIMETERS_PER_HOUR,
            allowed_units=units_of(Dimension.DEPTH_RATE),
            aggregation=Aggregation.PRECEDING_HOUR_SUM,
            text_key="rain_rate",
        ),
        WeatherVariable.SNOWFALL_RATE: VariableInfo(
            metric_unit=Unit.CENTIMETERS_PER_HOUR,
            allowed_units=units_of(Dimension.DEPTH_RATE),
            aggregation=Aggregation.PRECEDING_HOUR_SUM,
            text_key="snowfall_rate",
        ),
    },
)
