"""The trip option registry: what a driver may choose per trip, with defaults and bounds.

Defaults and allowed values come from the active rule set. Values arrive already converted to
metric at the API boundary; `resolve_options` checks them against the registry and never clamps.
The heatmap layer table also lives here (`docs/extensibility.md`).
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from planning import text
from planning.domain.values import TripOptions
from planning.errors import ErrorDetail, TripOptionsInvalid
from planning.keys import (
    CHECKPOINT_SPACING_TEXT_KEY,
    COMBINED_RISK_LAYER,
    COMBINED_RISK_TEXT_KEY,
    INCLUDE_REST_STOPS_TEXT_KEY,
    LOAD_WEIGHT_TEXT_KEY,
)
from rulesets.domain.schema import RuleSet, Spacing
from rulesets.domain.spacings import find_spacing
from shared.units import Unit
from shared.weather_variables import WEATHER_VARIABLES, WeatherVariable

MIN_LOAD_KG: Final = 0.0
MAX_LOAD_KG: Final = 50000.0
REST_STOPS_AVAILABLE: Final = True


class OptionTier(StrEnum):
    """Where the form shows an option: in the main form, or under "Advanced options"."""

    BASIC = "basic"
    ADVANCED = "advanced"


class TripOptionName(StrEnum):
    """Every trip parameter; also the request field that carries it."""

    CHECKPOINT_SPACING = "checkpoint_spacing"
    INCLUDE_REST_STOPS = "include_rest_stops"
    LOAD_WEIGHT = "load_weight"


@dataclass(frozen=True, slots=True)
class SpacingOption:
    """A choice among the rule set's checkpoint spacings; canonical unit km."""

    name: TripOptionName
    tier: OptionTier
    text_key: str
    available: bool
    unit: Unit
    choices: tuple[Spacing, ...]
    default: Spacing


@dataclass(frozen=True, slots=True)
class BooleanOption:
    """An on/off option. When not `available`, only the default is accepted."""

    name: TripOptionName
    tier: OptionTier
    text_key: str
    available: bool
    default: bool


@dataclass(frozen=True, slots=True)
class NumberOption:
    """A number in its canonical unit, inclusive bounds. `default` is None when `required`."""

    name: TripOptionName
    tier: OptionTier
    text_key: str
    available: bool
    unit: Unit
    required: bool
    default: float | None
    minimum: float
    maximum: float


@dataclass(frozen=True, slots=True)
class TripOptionRegistry:
    """Every trip parameter for one rule set."""

    checkpoint_spacing: SpacingOption
    include_rest_stops: BooleanOption
    load_weight: NumberOption


@dataclass(frozen=True, slots=True)
class TripOptionsInput:
    """Trip parameters as sent, converted to metric; None means omitted."""

    checkpoint_spacing_km: float | None = None
    include_rest_stops: bool | None = None
    load_kg: float | None = None


@dataclass(frozen=True, slots=True)
class HeatmapLayer:
    """A heatmap layer: which variable's values and levels it shows (None: combined level)."""

    key: str
    variable: WeatherVariable | None
    text_key: str


HEATMAP_LAYERS: Final = (
    HeatmapLayer(key=COMBINED_RISK_LAYER, variable=None, text_key=COMBINED_RISK_TEXT_KEY),
    *(
        HeatmapLayer(key=variable.value, variable=variable, text_key=info.text_key)
        for variable, info in WEATHER_VARIABLES.items()
    ),
)
DEFAULT_HEATMAP_LAYER: Final = COMBINED_RISK_LAYER


def build_options(rules: RuleSet) -> TripOptionRegistry:
    """The option registry for a rule set."""
    return TripOptionRegistry(
        checkpoint_spacing=SpacingOption(
            name=TripOptionName.CHECKPOINT_SPACING,
            tier=OptionTier.BASIC,
            text_key=CHECKPOINT_SPACING_TEXT_KEY,
            available=True,
            unit=Unit.KILOMETERS,
            choices=rules.checkpoint_spacings,
            default=rules.default_checkpoint_spacing,
        ),
        include_rest_stops=BooleanOption(
            name=TripOptionName.INCLUDE_REST_STOPS,
            tier=OptionTier.ADVANCED,
            text_key=INCLUDE_REST_STOPS_TEXT_KEY,
            available=REST_STOPS_AVAILABLE,
            default=rules.rest_rules.enabled and REST_STOPS_AVAILABLE,
        ),
        load_weight=NumberOption(
            name=TripOptionName.LOAD_WEIGHT,
            tier=OptionTier.BASIC,
            text_key=LOAD_WEIGHT_TEXT_KEY,
            available=True,
            unit=Unit.KILOGRAMS,
            required=True,
            default=None,
            minimum=MIN_LOAD_KG,
            maximum=MAX_LOAD_KG,
        ),
    )


def _resolve_spacing(
    option: SpacingOption, distance_km: float | None, problems: list[ErrorDetail]
) -> float:
    if distance_km is None:
        return option.default.km
    spacing = find_spacing(option.choices, distance_km)
    if spacing is None:
        problems.append(ErrorDetail(field=option.name, message=text.SPACING_NOT_ALLOWED))
        return option.default.km
    return spacing.km


def _resolve_boolean(
    option: BooleanOption, *, value: bool | None, problems: list[ErrorDetail]
) -> bool:
    if value is None:
        return option.default
    if not option.available and value is not option.default:
        problems.append(ErrorDetail(field=option.name, message=text.OPTION_UNAVAILABLE))
    return value


def _resolve_number(
    option: NumberOption, value: float | None, problems: list[ErrorDetail]
) -> float:
    if value is None:
        if option.default is None:
            problems.append(ErrorDetail(field=option.name, message=text.OPTION_REQUIRED))
            return option.minimum
        return option.default
    if not math.isfinite(value):
        problems.append(ErrorDetail(field=option.name, message=text.NOT_A_FINITE_NUMBER))
    elif not option.minimum <= value <= option.maximum:
        problems.append(
            ErrorDetail(
                field=option.name,
                message=text.out_of_bounds(option.minimum, option.maximum, option.unit.value),
            )
        )
    return value


def resolve_options(registry: TripOptionRegistry, raw: TripOptionsInput) -> TripOptions:
    """Check every sent value against the registry; omitted values take their default.

    Raises:
        TripOptionsInvalid: with one detail per rejected option.
    """
    problems: list[ErrorDetail] = []
    resolved = TripOptions(
        checkpoint_spacing_km=_resolve_spacing(
            registry.checkpoint_spacing, raw.checkpoint_spacing_km, problems
        ),
        include_rest_stops=_resolve_boolean(
            registry.include_rest_stops, value=raw.include_rest_stops, problems=problems
        ),
        load_kg=_resolve_number(registry.load_weight, raw.load_kg, problems),
    )
    if problems:
        raise TripOptionsInvalid(tuple(problems))
    return resolved
