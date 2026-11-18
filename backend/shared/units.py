"""Units the app accepts, with exact factors, and the one conversion function.

Each unit belongs to a dimension and has an exact factor to that dimension's base unit. Converting
between two units of the same dimension multiplies by one factor and divides by the other.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

KM_PER_MILE = 1.609344
MM_PER_INCH = 25.4
KG_PER_POUND = 0.45359237
KMH_PER_METER_PER_SECOND = 3.6
KMH_PER_KNOT = 1.852
KM_PER_METER = 0.001
MM_PER_CM = 10.0
KG_PER_METRIC_TON = 1000.0
MEASURE_DECIMALS = 9


class Dimension(StrEnum):
    """What a unit measures."""

    SPEED = "speed"
    DISTANCE = "distance"
    DEPTH_RATE = "depth_rate"
    MASS = "mass"


class Unit(StrEnum):
    """Every unit a value may be entered or returned in."""

    KILOMETERS_PER_HOUR = "km/h"
    MILES_PER_HOUR = "mph"
    METERS_PER_SECOND = "m/s"
    KNOTS = "kn"
    KILOMETERS = "km"
    MILES = "mi"
    METERS = "m"
    MILLIMETERS_PER_HOUR = "mm/h"
    CENTIMETERS_PER_HOUR = "cm/h"
    INCHES_PER_HOUR = "in/h"
    KILOGRAMS = "kg"
    POUNDS = "lb"
    METRIC_TONS = "t"


@dataclass(frozen=True, slots=True)
class UnitInfo:
    """A unit's dimension and its exact factor to the dimension's base unit."""

    dimension: Dimension
    factor_to_base: float


UNITS: Mapping[Unit, UnitInfo] = MappingProxyType(
    {
        Unit.KILOMETERS_PER_HOUR: UnitInfo(Dimension.SPEED, 1.0),
        Unit.MILES_PER_HOUR: UnitInfo(Dimension.SPEED, KM_PER_MILE),
        Unit.METERS_PER_SECOND: UnitInfo(Dimension.SPEED, KMH_PER_METER_PER_SECOND),
        Unit.KNOTS: UnitInfo(Dimension.SPEED, KMH_PER_KNOT),
        Unit.KILOMETERS: UnitInfo(Dimension.DISTANCE, 1.0),
        Unit.MILES: UnitInfo(Dimension.DISTANCE, KM_PER_MILE),
        Unit.METERS: UnitInfo(Dimension.DISTANCE, KM_PER_METER),
        Unit.MILLIMETERS_PER_HOUR: UnitInfo(Dimension.DEPTH_RATE, 1.0),
        Unit.CENTIMETERS_PER_HOUR: UnitInfo(Dimension.DEPTH_RATE, MM_PER_CM),
        Unit.INCHES_PER_HOUR: UnitInfo(Dimension.DEPTH_RATE, MM_PER_INCH),
        Unit.KILOGRAMS: UnitInfo(Dimension.MASS, 1.0),
        Unit.POUNDS: UnitInfo(Dimension.MASS, KG_PER_POUND),
        Unit.METRIC_TONS: UnitInfo(Dimension.MASS, KG_PER_METRIC_TON),
    },
)

METRIC_UNIT_BY_DIMENSION: Mapping[Dimension, Unit] = MappingProxyType(
    {
        Dimension.SPEED: Unit.KILOMETERS_PER_HOUR,
        Dimension.DISTANCE: Unit.KILOMETERS,
        Dimension.DEPTH_RATE: Unit.MILLIMETERS_PER_HOUR,
        Dimension.MASS: Unit.KILOGRAMS,
    },
)


class IncompatibleUnitsError(ValueError):
    """The two units measure different dimensions."""

    def __init__(self, from_unit: Unit, to_unit: Unit) -> None:
        """Name both units."""
        super().__init__(f"{from_unit} -> {to_unit}")


def round_measure(value: float) -> float:
    """Round a measured or converted value to `MEASURE_DECIMALS` decimals.

    Every converted threshold and every provider value passes through this, so a value exactly on a
    band edge compares equal to the edge instead of differing by floating-point noise.
    """
    return round(value, MEASURE_DECIMALS) + 0.0


def units_of(dimension: Dimension) -> frozenset[Unit]:
    """Every unit that measures the dimension."""
    return frozenset(unit for unit, info in UNITS.items() if info.dimension is dimension)


def convert(value: float, from_unit: Unit, to_unit: Unit) -> float:
    """Convert a value between two units of the same dimension.

    Raises:
        IncompatibleUnitsError: the units measure different dimensions.
    """
    source = UNITS[from_unit]
    target = UNITS[to_unit]
    if source.dimension is not target.dimension:
        raise IncompatibleUnitsError(from_unit, to_unit)
    if from_unit is to_unit:
        return value
    return round_measure(value * source.factor_to_base / target.factor_to_base)
