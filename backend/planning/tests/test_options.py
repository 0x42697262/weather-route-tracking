import dataclasses

import pytest

from planning.domain.options import (
    DEFAULT_HEATMAP_LAYER,
    HEATMAP_LAYERS,
    MAX_LOAD_KG,
    OptionTier,
    TripOptionName,
    TripOptionRegistry,
    TripOptionsInput,
    build_options,
    resolve_options,
)
from planning.domain.values import TripOptions
from planning.errors import ErrorCode, TripOptionsInvalid
from rulesets.domain.defaults import default_rule_set_document
from rulesets.domain.validator import validate_rule_set
from shared.units import Unit
from shared.weather_variables import WEATHER_VARIABLES

RULES = validate_rule_set(default_rule_set_document())
REGISTRY = build_options(RULES)
UNAVAILABLE_REST = dataclasses.replace(
    REGISTRY,
    include_rest_stops=dataclasses.replace(
        REGISTRY.include_rest_stops, available=False, default=False
    ),
)
TWENTY_FIVE_MILES_KM = 40.2336
TEN_MILES_KM = 16.09344


def _problem_fields(registry: TripOptionRegistry, raw: TripOptionsInput) -> list[str]:
    with pytest.raises(TripOptionsInvalid) as caught:
        resolve_options(registry, raw)
    assert caught.value.code is ErrorCode.INVALID_REQUEST
    return [detail.field for detail in caught.value.details]


def test_registry_takes_spacings_and_defaults_from_the_rule_set() -> None:
    spacing = REGISTRY.checkpoint_spacing

    assert spacing.choices == RULES.checkpoint_spacings
    assert spacing.default == RULES.default_checkpoint_spacing
    assert spacing.unit is Unit.KILOMETERS
    assert spacing.tier is OptionTier.BASIC
    assert REGISTRY.include_rest_stops.tier is OptionTier.ADVANCED
    assert REGISTRY.load_weight.unit is Unit.KILOGRAMS
    assert REGISTRY.load_weight.required is True


def test_rest_stops_are_available_and_default_to_the_rule_set_switch() -> None:
    assert REGISTRY.include_rest_stops.available is True
    assert REGISTRY.include_rest_stops.default is RULES.rest_rules.enabled


def test_omitted_options_take_their_defaults() -> None:
    resolved = resolve_options(REGISTRY, TripOptionsInput(load_kg=1000.0))

    assert resolved == TripOptions(
        checkpoint_spacing_km=RULES.default_checkpoint_spacing.km,
        include_rest_stops=RULES.rest_rules.enabled,
        load_kg=1000.0,
    )
    assert resolved.checkpoint_spacing_km == pytest.approx(TWENTY_FIVE_MILES_KM)


def test_an_allowed_spacing_is_accepted_in_km() -> None:
    resolved = resolve_options(
        REGISTRY, TripOptionsInput(checkpoint_spacing_km=TEN_MILES_KM, load_kg=0.0)
    )

    assert resolved.checkpoint_spacing_km == pytest.approx(TEN_MILES_KM)


@pytest.mark.parametrize("load_kg", [0.0, MAX_LOAD_KG])
def test_load_bounds_are_inclusive(load_kg: float) -> None:
    assert resolve_options(REGISTRY, TripOptionsInput(load_kg=load_kg)).load_kg == load_kg


@pytest.mark.parametrize(
    ("raw", "field"),
    [
        (TripOptionsInput(), TripOptionName.LOAD_WEIGHT),
        (TripOptionsInput(load_kg=-0.001), TripOptionName.LOAD_WEIGHT),
        (TripOptionsInput(load_kg=MAX_LOAD_KG + 0.001), TripOptionName.LOAD_WEIGHT),
        (TripOptionsInput(load_kg=float("nan")), TripOptionName.LOAD_WEIGHT),
        (
            TripOptionsInput(checkpoint_spacing_km=30.0, load_kg=1.0),
            TripOptionName.CHECKPOINT_SPACING,
        ),
        (
            TripOptionsInput(include_rest_stops=True, load_kg=1.0),
            TripOptionName.INCLUDE_REST_STOPS,
        ),
    ],
)
def test_out_of_registry_values_are_rejected_not_clamped(
    raw: TripOptionsInput, field: TripOptionName
) -> None:
    assert _problem_fields(UNAVAILABLE_REST, raw) == [field]


def test_every_rejected_option_is_listed() -> None:
    raw = TripOptionsInput(checkpoint_spacing_km=30.0, include_rest_stops=True, load_kg=-1.0)

    assert _problem_fields(UNAVAILABLE_REST, raw) == [
        TripOptionName.CHECKPOINT_SPACING,
        TripOptionName.INCLUDE_REST_STOPS,
        TripOptionName.LOAD_WEIGHT,
    ]


def test_an_available_rest_option_accepts_both_values() -> None:
    rest = dataclasses.replace(REGISTRY.include_rest_stops, available=True, default=True)
    registry = dataclasses.replace(REGISTRY, include_rest_stops=rest)

    off = resolve_options(registry, TripOptionsInput(include_rest_stops=False, load_kg=1.0))
    default = resolve_options(registry, TripOptionsInput(load_kg=1.0))

    assert off.include_rest_stops is False
    assert default.include_rest_stops is True


def test_heatmap_layers_are_the_combined_risk_then_one_per_variable() -> None:
    assert HEATMAP_LAYERS[0].key == DEFAULT_HEATMAP_LAYER
    assert HEATMAP_LAYERS[0].variable is None
    assert [layer.variable for layer in HEATMAP_LAYERS[1:]] == list(WEATHER_VARIABLES)
    assert [layer.key for layer in HEATMAP_LAYERS] == [
        "risk",
        "wind_speed",
        "rain_rate",
        "snowfall_rate",
    ]
