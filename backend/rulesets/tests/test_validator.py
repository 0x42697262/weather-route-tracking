from collections.abc import Callable
from typing import Any

import pytest

from rulesets.domain.defaults import default_rule_set_document
from rulesets.domain.schema import StretchMethod
from rulesets.domain.validator import RuleSetInvalid, validate_rule_set
from shared.risk_levels import RiskLevel
from shared.units import Unit
from shared.weather_variables import WeatherVariable

type Document = dict[str, Any]


def _document() -> Document:
    return default_rule_set_document()


def _problem_fields(document: object) -> list[str]:
    with pytest.raises(RuleSetInvalid) as caught:
        validate_rule_set(document)
    return [problem.field for problem in caught.value.problems]


def test_default_document_is_valid_and_converted_to_metric() -> None:
    rules = validate_rule_set(default_rule_set_document())

    wind, rain, snow = rules.conditions
    assert wind.variable is WeatherVariable.WIND_SPEED
    assert [band.from_value for band in wind.bands] == pytest.approx(
        [40.2336, 56.32704, 72.42048, 88.51392]
    )
    assert [band.level for band in wind.bands] == [
        RiskLevel.MODERATE,
        RiskLevel.HIGH,
        RiskLevel.SEVERE,
        RiskLevel.NO_TRAVEL,
    ]
    assert [band.from_value for band in rain.bands] == pytest.approx([2.54, 6.35, 12.7, 25.4])
    assert [band.inclusive for band in rain.bands] == [True, True, True, False]
    assert [band.from_value for band in snow.bands] == pytest.approx([1.27, 2.54, 5.08, 7.62])
    first_rule, second_rule = rules.load_rules
    assert first_rule.load_over_kg == pytest.approx(13607.7711)
    assert (first_rule.from_value, first_rule.to_value) == pytest.approx((72.42048, 88.51392))
    assert first_rule.level is RiskLevel.NO_TRAVEL
    assert second_rule.load_over_kg == pytest.approx(18143.6948)
    assert rules.truck_speed_factor == 1.0
    assert rules.truck_max_speed_kmh == pytest.approx(104.60736)
    assert rules.empty_vehicle_weight_kg == pytest.approx(14741.752025)
    assert rules.rest_rules.max_driving_before_break_s == 8 * 3600
    assert rules.rest_rules.break_s == 30 * 60
    assert rules.rest_rules.max_driving_per_shift_s == 11 * 3600
    assert rules.rest_rules.max_shift_s == 14 * 3600
    assert rules.rest_rules.off_duty_s == 10 * 3600
    assert rules.rest_rules.enabled is True
    assert rules.stretch_method is StretchMethod.WORSE_END
    assert rules.ferry_level is None
    assert [spacing.km for spacing in rules.checkpoint_spacings] == pytest.approx(
        [16.09344, 40.2336, 80.4672]
    )
    assert rules.default_checkpoint_spacing.value == 25
    assert rules.default_checkpoint_spacing.unit is Unit.MILES


def test_default_document_is_a_fresh_copy() -> None:
    first = _document()
    first["conditions"].clear()

    assert default_rule_set_document()["conditions"]


def test_metric_entry_and_no_speed_cap_are_accepted() -> None:
    document = _document()
    document["truck_max_speed"] = None
    document["ferry_level"] = "high"
    document["conditions"][0]["unit"] = "km/h"

    rules = validate_rule_set(document)

    assert rules.truck_max_speed_kmh is None
    assert rules.ferry_level is RiskLevel.HIGH
    assert rules.conditions[0].bands[0].from_value == 25


def _set(path: tuple[str | int, ...], new_value: object) -> Callable[[Document], None]:
    def mutate(document: Document) -> None:
        target: Any = document
        for step in path[:-1]:
            target = target[step]
        target[path[-1]] = new_value

    return mutate


def _delete(path: tuple[str | int, ...]) -> Callable[[Document], None]:
    def mutate(document: Document) -> None:
        target: Any = document
        for step in path[:-1]:
            target = target[step]
        del target[path[-1]]

    return mutate


def _append(
    path: tuple[str | int, ...], item: object, times: int = 1
) -> Callable[[Document], None]:
    def mutate(document: Document) -> None:
        target: Any = document
        for step in path:
            target = target[step]
        target.extend([item] * times)

    return mutate


def _wind_band(level: str, from_value: float) -> dict[str, object]:
    return {"level": level, "from": from_value, "inclusive": True}


REJECTIONS: list[tuple[str, Callable[[Document], None], str]] = [
    ("missing key", _delete(("stretch_method",)), "stretch_method"),
    ("extra key", _set(("color",), "red"), "color"),
    ("missing nested key", _delete(("rest_rules", "break_minutes")), "rest_rules.break_minutes"),
    ("extra nested key", _set(("conditions", 0, "gusts"), 1), "conditions[0].gusts"),
    ("unknown variable", _set(("conditions", 0, "variable"), "fog"), "conditions[0].variable"),
    ("unit of wrong kind", _set(("conditions", 0, "unit"), "in/h"), "conditions[0].unit"),
    (
        "unknown level",
        _set(("conditions", 0, "bands", 0, "level"), "extreme"),
        "conditions[0].bands[0].level",
    ),
    (
        "low band",
        _set(("conditions", 0, "bands", 0, "level"), "low"),
        "conditions[0].bands[0].level",
    ),
    (
        "bound not ascending",
        _set(("conditions", 0, "bands", 1, "from"), 25),
        "conditions[0].bands[1].from",
    ),
    (
        "level not ascending",
        _set(("conditions", 0, "bands", 1, "level"), "moderate"),
        "conditions[0].bands[1].level",
    ),
    (
        "band bound not a number",
        _set(("conditions", 0, "bands", 0, "from"), "25"),
        "conditions[0].bands[0].from",
    ),
    (
        "inclusive not a boolean",
        _set(("conditions", 0, "bands", 0, "inclusive"), 1),
        "conditions[0].bands[0].inclusive",
    ),
    ("empty bands", _set(("conditions", 0, "bands"), []), "conditions[0].bands"),
    (
        "too many bands",
        _append(("conditions", 0, "bands"), _wind_band("no_travel", 99), 7),
        "conditions[0].bands",
    ),
    ("empty conditions", _set(("conditions",), []), "conditions"),
    (
        "duplicate variable",
        lambda document: document["conditions"].append(dict(document["conditions"][0])),
        "conditions[3].variable",
    ),
    ("load rule range empty", _set(("load_rules", 0, "from"), 55), "load_rules[0].from"),
    (
        "load weight not positive",
        _set(("load_rules", 0, "load_over", "value"), 0),
        "load_rules[0].load_over.value",
    ),
    (
        "load weight unit of wrong kind",
        _set(("load_rules", 0, "load_over", "unit"), "mi"),
        "load_rules[0].load_over.unit",
    ),
    ("load rule level", _set(("load_rules", 0, "level"), "awful"), "load_rules[0].level"),
    (
        "too many load rules",
        lambda document: document["load_rules"].extend([document["load_rules"][0]] * 19),
        "load_rules",
    ),
    ("speed factor too low", _set(("truck_speed_factor",), 0.1), "truck_speed_factor"),
    ("speed factor too high", _set(("truck_speed_factor",), 2.0), "truck_speed_factor"),
    ("speed factor a boolean", _set(("truck_speed_factor",), new_value=True), "truck_speed_factor"),
    ("speed cap too high", _set(("truck_max_speed", "value"), 200), "truck_max_speed"),
    ("speed cap too low", _set(("truck_max_speed", "value"), 10), "truck_max_speed"),
    (
        "speed cap unit of wrong kind",
        _set(("truck_max_speed", "unit"), "lb"),
        "truck_max_speed.unit",
    ),
    (
        "empty weight too high",
        _set(("empty_vehicle_weight", "value"), 900000),
        "empty_vehicle_weight",
    ),
    ("empty weight too low", _set(("empty_vehicle_weight", "value"), 100), "empty_vehicle_weight"),
    ("rest value zero", _set(("rest_rules", "off_duty_hours"), 0), "rest_rules.off_duty_hours"),
    ("rest switch not a boolean", _set(("rest_rules", "enabled"), "yes"), "rest_rules.enabled"),
    (
        "break limit above shift driving",
        _set(("rest_rules", "max_driving_before_break_hours"), 12),
        "rest_rules.max_driving_before_break_hours",
    ),
    (
        "shift driving above shift length",
        _set(("rest_rules", "max_driving_per_shift_hours"), 15),
        "rest_rules.max_driving_per_shift_hours",
    ),
    ("unknown stretch method", _set(("stretch_method",), "average"), "stretch_method"),
    ("unknown ferry level", _set(("ferry_level",), "calm"), "ferry_level"),
    ("empty spacings", _set(("checkpoint_spacings",), []), "checkpoint_spacings"),
    (
        "too many spacings",
        lambda document: document["checkpoint_spacings"].extend(
            [{"value": value, "unit": "km"} for value in range(1, 9)]
        ),
        "checkpoint_spacings",
    ),
    (
        "duplicate spacing",
        _set(("checkpoint_spacings", 1), {"value": 16.09344, "unit": "km"}),
        "checkpoint_spacings[1]",
    ),
    (
        "spacing not positive",
        _set(("checkpoint_spacings", 0, "value"), -10),
        "checkpoint_spacings[0].value",
    ),
    (
        "default spacing not in the list",
        _set(("default_checkpoint_spacing", "value"), 30),
        "default_checkpoint_spacing",
    ),
    ("conditions not a list", _set(("conditions",), {}), "conditions"),
    ("rest rules not an object", _set(("rest_rules",), []), "rest_rules"),
    ("infinite number", _set(("truck_speed_factor",), float("inf")), "truck_speed_factor"),
]


@pytest.mark.parametrize(
    ("mutate", "field"),
    [(mutate, field) for _, mutate, field in REJECTIONS],
    ids=[reason for reason, _, _ in REJECTIONS],
)
def test_each_rejection_names_its_field(mutate: Callable[[Document], None], field: str) -> None:
    document = _document()
    mutate(document)

    assert field in _problem_fields(document)


@pytest.mark.parametrize("version", [3, 0, "1", None, True])
def test_unknown_schema_version_is_reported_alone(version: object) -> None:
    document = _document()
    document["schema_version"] = version
    document["stretch_method"] = "average"

    assert _problem_fields(document) == ["schema_version"]


def test_a_document_that_is_not_an_object_is_rejected() -> None:
    assert _problem_fields([1, 2]) == ["$"]


def test_every_problem_is_reported_at_once() -> None:
    document = _document()
    document["conditions"][0]["variable"] = "fog"
    document["truck_speed_factor"] = 9
    document["ferry_level"] = "calm"
    del document["load_rules"]

    fields = _problem_fields(document)

    assert set(fields) == {
        "conditions[0].variable",
        "truck_speed_factor",
        "ferry_level",
        "load_rules",
    }


def test_default_limits_unknown_share_to_a_quarter() -> None:
    assert validate_rule_set(_document()).max_unknown_share == 0.25


def test_null_unknown_share_means_no_limit() -> None:
    document = _document()
    document["max_unknown_share"] = None

    assert validate_rule_set(document).max_unknown_share is None


@pytest.mark.parametrize("share", [-0.01, 1.01, "0.25", True])
def test_unknown_share_outside_zero_to_one_is_rejected(share: object) -> None:
    document = _document()
    document["max_unknown_share"] = share

    assert _problem_fields(document) == ["max_unknown_share"]


def test_schema_two_requires_the_unknown_share() -> None:
    document = _document()
    del document["max_unknown_share"]

    assert _problem_fields(document) == ["max_unknown_share"]


def test_schema_one_documents_stay_valid_with_no_unknown_limit() -> None:
    document = _document()
    del document["max_unknown_share"]
    document["schema_version"] = 1

    assert validate_rule_set(document).max_unknown_share is None


def test_schema_one_documents_reject_the_new_field() -> None:
    document = _document()
    document["schema_version"] = 1

    assert _problem_fields(document) == ["max_unknown_share"]
