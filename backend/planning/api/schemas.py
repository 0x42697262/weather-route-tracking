"""Response schemas of `GET /api/v1/options` (the contract)."""

from ninja import Schema

from planning.domain.options import (
    DEFAULT_HEATMAP_LAYER,
    HEATMAP_LAYERS,
    BooleanOption,
    NumberOption,
    OptionTier,
    SpacingOption,
    TripOptionName,
    TripOptionRegistry,
)
from planning.domain.risk_constants import FORECAST_WINDOW_HOURS
from planning.services.attribution import Attribution
from planning.services.checks import latest_departure_hours
from planning.services.constants import DEPARTURE_PAST_TOLERANCE, ROUTES_TARGET, SECONDS_PER_MINUTE
from rulesets.domain.schema import Spacing, StretchMethod, VersionedRuleSet
from shared.risk_levels import LEVELS_BY_SCORE, RISK_LEVELS, RiskLevel
from shared.units import Unit
from shared.weather_variables import WEATHER_VARIABLES, WeatherVariable


class SpacingOut(Schema):
    """A checkpoint spacing as staff entered it, and in km."""

    value: float
    unit: Unit
    km: float


class SpacingOptionOut(Schema):
    """The checkpoint spacing choice."""

    name: TripOptionName
    tier: OptionTier
    text_key: str
    available: bool
    unit: Unit
    choices: list[SpacingOut]
    default: SpacingOut


class BooleanOptionOut(Schema):
    """An on/off option. When `available` is false, only `default` is accepted."""

    name: TripOptionName
    tier: OptionTier
    text_key: str
    available: bool
    default: bool


class NumberOptionOut(Schema):
    """A number in `unit`, with inclusive bounds. `default` is null when `required`."""

    name: TripOptionName
    tier: OptionTier
    text_key: str
    available: bool
    unit: Unit
    required: bool
    default: float | None
    minimum: float
    maximum: float


class TripOptionsOut(Schema):
    """Every trip parameter."""

    checkpoint_spacing: SpacingOptionOut
    include_rest_stops: BooleanOptionOut
    load_weight: NumberOptionOut


class RiskLevelOut(Schema):
    """One row of the risk level table."""

    key: RiskLevel
    score: int
    ranked: bool
    blocks_recommendation: bool
    text_key: str
    color_key: str


class WeatherVariableOut(Schema):
    """One row of the weather condition table."""

    key: WeatherVariable
    metric_unit: Unit
    text_key: str


class HeatmapLayerOut(Schema):
    """A heatmap layer; `variable` is null for the combined risk."""

    key: str
    variable: WeatherVariable | None
    text_key: str


class HeatmapLayersOut(Schema):
    """The heatmap layers and the one shown first."""

    default: str
    layers: list[HeatmapLayerOut]


class AttributionOut(Schema):
    """A notice the map shows where a provider's data is displayed; `url` links it if set."""

    text: str
    url: str | None


class DepartureWindowOut(Schema):
    """The departures a trip accepts, relative to now."""

    past_tolerance_minutes: int
    max_hours_ahead: int


class OptionsOut(Schema):
    """What the driver may choose, and the tables the frontend renders by iterating."""

    rule_set_version: int
    forecast_window_hours: int
    stretch_method: StretchMethod
    routes_target: int
    departure_window: DepartureWindowOut
    attribution: list[AttributionOut]
    options: TripOptionsOut
    risk_levels: list[RiskLevelOut]
    weather_variables: list[WeatherVariableOut]
    heatmap_layers: HeatmapLayersOut


def _spacing_out(spacing: Spacing) -> SpacingOut:
    return SpacingOut(value=spacing.value, unit=spacing.unit, km=spacing.km)


def _spacing_option_out(option: SpacingOption) -> SpacingOptionOut:
    return SpacingOptionOut(
        name=option.name,
        tier=option.tier,
        text_key=option.text_key,
        available=option.available,
        unit=option.unit,
        choices=[_spacing_out(choice) for choice in option.choices],
        default=_spacing_out(option.default),
    )


def _boolean_option_out(option: BooleanOption) -> BooleanOptionOut:
    return BooleanOptionOut(
        name=option.name,
        tier=option.tier,
        text_key=option.text_key,
        available=option.available,
        default=option.default,
    )


def _number_option_out(option: NumberOption) -> NumberOptionOut:
    return NumberOptionOut(
        name=option.name,
        tier=option.tier,
        text_key=option.text_key,
        available=option.available,
        unit=option.unit,
        required=option.required,
        default=option.default,
        minimum=option.minimum,
        maximum=option.maximum,
    )


def options_out(
    versioned: VersionedRuleSet,
    registry: TripOptionRegistry,
    attributions: tuple[Attribution, ...],
    forecast_horizon_hours: int,
) -> OptionsOut:
    """The options response for a rule set version, its registry and the chosen providers."""
    return OptionsOut(
        rule_set_version=versioned.version,
        forecast_window_hours=FORECAST_WINDOW_HOURS,
        stretch_method=versioned.rules.stretch_method,
        routes_target=ROUTES_TARGET,
        departure_window=DepartureWindowOut(
            past_tolerance_minutes=int(
                DEPARTURE_PAST_TOLERANCE.total_seconds() // SECONDS_PER_MINUTE
            ),
            max_hours_ahead=latest_departure_hours(forecast_horizon_hours),
        ),
        attribution=[AttributionOut(text=item.text, url=item.url) for item in attributions],
        options=TripOptionsOut(
            checkpoint_spacing=_spacing_option_out(registry.checkpoint_spacing),
            include_rest_stops=_boolean_option_out(registry.include_rest_stops),
            load_weight=_number_option_out(registry.load_weight),
        ),
        risk_levels=[
            RiskLevelOut(
                key=level,
                score=RISK_LEVELS[level].score,
                ranked=RISK_LEVELS[level].ranked,
                blocks_recommendation=RISK_LEVELS[level].blocks_recommendation,
                text_key=RISK_LEVELS[level].text_key,
                color_key=RISK_LEVELS[level].color_key,
            )
            for level in LEVELS_BY_SCORE
        ],
        weather_variables=[
            WeatherVariableOut(key=variable, metric_unit=info.metric_unit, text_key=info.text_key)
            for variable, info in WEATHER_VARIABLES.items()
        ],
        heatmap_layers=HeatmapLayersOut(
            default=DEFAULT_HEATMAP_LAYER,
            layers=[
                HeatmapLayerOut(key=layer.key, variable=layer.variable, text_key=layer.text_key)
                for layer in HEATMAP_LAYERS
            ],
        ),
    )
