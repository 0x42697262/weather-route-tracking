"""The validated rule set: frozen, metric-only objects built by `validate_rule_set`.

Planning code only ever sees these. Values are already converted to the metric unit of their
variable (`shared.weather_variables`) or to km, km/h, kg and seconds.
"""

from dataclasses import dataclass
from enum import StrEnum

from shared.risk_levels import RiskLevel
from shared.units import Unit
from shared.weather_variables import WeatherVariable


class StretchMethod(StrEnum):
    """How a stretch between two samples gets its level (`docs/risk-model.md`)."""

    WORSE_END = "worse_end"
    REFINE = "refine"


@dataclass(frozen=True, slots=True)
class Band:
    """A lower bound for a level. A value reaches it when above it, or equal and inclusive."""

    level: RiskLevel
    from_value: float
    inclusive: bool


@dataclass(frozen=True, slots=True)
class Condition:
    """A variable and its bands, ascending. Values below the first band are the lowest level."""

    variable: WeatherVariable
    bands: tuple[Band, ...]


@dataclass(frozen=True, slots=True)
class LoadRule:
    """When `from_value <= value < to_value` and the load is strictly over `load_over_kg`, the
    level is at least `level`."""

    variable: WeatherVariable
    from_value: float
    to_value: float
    load_over_kg: float
    level: RiskLevel


@dataclass(frozen=True, slots=True)
class RestRules:
    """The driving-and-rest clock, in seconds. `enabled` is the default of the trip option."""

    enabled: bool
    max_driving_before_break_s: float
    break_s: float
    max_driving_per_shift_s: float
    max_shift_s: float
    off_duty_s: float


@dataclass(frozen=True, slots=True)
class Spacing:
    """An allowed checkpoint spacing: as staff entered it, and in km."""

    value: float
    unit: Unit
    km: float


@dataclass(frozen=True, slots=True)
class RuleSet:
    """Every business rule of one rule set version, in metric units."""

    conditions: tuple[Condition, ...]
    load_rules: tuple[LoadRule, ...]
    truck_speed_factor: float
    truck_max_speed_kmh: float | None
    empty_vehicle_weight_kg: float
    rest_rules: RestRules
    stretch_method: StretchMethod
    ferry_level: RiskLevel | None
    max_unknown_share: float | None
    checkpoint_spacings: tuple[Spacing, ...]
    default_checkpoint_spacing: Spacing


@dataclass(frozen=True, slots=True)
class VersionedRuleSet:
    """A rule set and the version number that produced it."""

    version: int
    rules: RuleSet
