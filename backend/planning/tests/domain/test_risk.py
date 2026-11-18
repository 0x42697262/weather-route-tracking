from dataclasses import replace

import pytest

from planning.domain.risk import (
    Classification,
    ConditionLevel,
    DecisionKind,
    classify,
    decided_by,
    rule_set_variables,
)
from rulesets.domain.defaults import default_rule_set_document
from rulesets.domain.schema import (
    Band,
    Condition,
    LoadRule,
    RestRules,
    RuleSet,
    Spacing,
    StretchMethod,
)
from rulesets.domain.validator import validate_rule_set
from shared.risk_levels import RiskLevel
from shared.units import Unit, convert
from shared.weather_variables import WEATHER_VARIABLES, WeatherVariable

WIND = WeatherVariable.WIND_SPEED
RAIN = WeatherVariable.RAIN_RATE
SNOW = WeatherVariable.SNOWFALL_RATE
MPH = Unit.MILES_PER_HOUR
IN_H = Unit.INCHES_PER_HOUR
LB = Unit.POUNDS

LOW = RiskLevel.LOW
MODERATE = RiskLevel.MODERATE
HIGH = RiskLevel.HIGH
SEVERE = RiskLevel.SEVERE
NO_TRAVEL = RiskLevel.NO_TRAVEL

DEFAULT_BANDS = {
    WIND: (
        MPH,
        ((MODERATE, 25, True), (HIGH, 35, True), (SEVERE, 45, True), (NO_TRAVEL, 55, True)),
    ),
    RAIN: (
        IN_H,
        (
            (MODERATE, 0.10, True),
            (HIGH, 0.25, True),
            (SEVERE, 0.50, True),
            (NO_TRAVEL, 1.00, False),
        ),
    ),
    SNOW: (
        IN_H,
        ((MODERATE, 0.5, True), (HIGH, 1.0, True), (SEVERE, 2.0, True), (NO_TRAVEL, 3.0, False)),
    ),
}
DEFAULT_LOAD_RULES = ((WIND, MPH, 45, 55, 30000, NO_TRAVEL), (WIND, MPH, 35, 45, 40000, SEVERE))


def _metric(variable: WeatherVariable, value: float, unit: Unit) -> float:
    return convert(value, unit, WEATHER_VARIABLES[variable].metric_unit)


def _kg(pounds: float) -> float:
    return convert(pounds, LB, Unit.KILOGRAMS)


def _rule_set(
    load_rules: tuple[tuple[WeatherVariable, Unit, float, float, float, RiskLevel], ...] = (
        DEFAULT_LOAD_RULES
    ),
) -> RuleSet:
    spacing = Spacing(value=25, unit=Unit.MILES, km=convert(25, Unit.MILES, Unit.KILOMETERS))
    return RuleSet(
        conditions=tuple(
            Condition(
                variable=variable,
                bands=tuple(
                    Band(level, _metric(variable, bound, unit), inclusive)
                    for level, bound, inclusive in bands
                ),
            )
            for variable, (unit, bands) in DEFAULT_BANDS.items()
        ),
        load_rules=tuple(
            LoadRule(
                variable=variable,
                from_value=_metric(variable, low, unit),
                to_value=_metric(variable, high, unit),
                load_over_kg=_kg(pounds),
                level=level,
            )
            for variable, unit, low, high, pounds, level in load_rules
        ),
        truck_speed_factor=1.0,
        truck_max_speed_kmh=None,
        empty_vehicle_weight_kg=_kg(32500),
        rest_rules=RestRules(
            enabled=False,
            max_driving_before_break_s=28800,
            break_s=1800,
            max_driving_per_shift_s=39600,
            max_shift_s=50400,
            off_duty_s=36000,
        ),
        stretch_method=StretchMethod.WORSE_END,
        ferry_level=None,
        max_unknown_share=None,
        checkpoint_spacings=(spacing,),
        default_checkpoint_spacing=spacing,
    )


RULES = _rule_set()


def _values(
    wind_mph: float = 0, rain_in_h: float = 0, snow_in_h: float = 0
) -> dict[WeatherVariable, float | None]:
    return {
        WIND: _metric(WIND, wind_mph, MPH),
        RAIN: _metric(RAIN, rain_in_h, IN_H),
        SNOW: _metric(SNOW, snow_in_h, IN_H),
    }


def _entered(variable: WeatherVariable, value: float) -> dict[WeatherVariable, float | None]:
    values = _values()
    values[variable] = _metric(variable, value, DEFAULT_BANDS[variable][0])
    return values


BAND_EDGES = [
    (WIND, 0, LOW),
    (WIND, 24.99, LOW),
    (WIND, 25, MODERATE),
    (WIND, 25.01, MODERATE),
    (WIND, 34.99, MODERATE),
    (WIND, 35, HIGH),
    (WIND, 35.01, HIGH),
    (WIND, 44.99, HIGH),
    (WIND, 45, SEVERE),
    (WIND, 45.01, SEVERE),
    (WIND, 54.99, SEVERE),
    (WIND, 55, NO_TRAVEL),
    (WIND, 55.01, NO_TRAVEL),
    (RAIN, 0, LOW),
    (RAIN, 0.099, LOW),
    (RAIN, 0.10, MODERATE),
    (RAIN, 0.101, MODERATE),
    (RAIN, 0.249, MODERATE),
    (RAIN, 0.25, HIGH),
    (RAIN, 0.251, HIGH),
    (RAIN, 0.499, HIGH),
    (RAIN, 0.50, SEVERE),
    (RAIN, 0.501, SEVERE),
    (RAIN, 0.999, SEVERE),
    (RAIN, 1.00, SEVERE),
    (RAIN, 1.001, NO_TRAVEL),
    (SNOW, 0, LOW),
    (SNOW, 0.499, LOW),
    (SNOW, 0.5, MODERATE),
    (SNOW, 0.501, MODERATE),
    (SNOW, 0.999, MODERATE),
    (SNOW, 1.0, HIGH),
    (SNOW, 1.001, HIGH),
    (SNOW, 1.999, HIGH),
    (SNOW, 2.0, SEVERE),
    (SNOW, 2.001, SEVERE),
    (SNOW, 2.999, SEVERE),
    (SNOW, 3.0, SEVERE),
    (SNOW, 3.001, NO_TRAVEL),
]


@pytest.mark.parametrize(("variable", "entered", "expected"), BAND_EDGES)
def test_band_edges_in_entered_units(
    variable: WeatherVariable, entered: float, expected: RiskLevel
) -> None:
    result = classify(_entered(variable, entered), 0, RULES)

    assert result.level is expected
    expected_decided_by = None if expected is LOW else decided_by(DecisionKind.BAND, variable)
    assert result.decided_by == expected_decided_by


@pytest.mark.parametrize(("variable", "entered", "expected"), BAND_EDGES)
def test_condition_level_matches_band(
    variable: WeatherVariable, entered: float, expected: RiskLevel
) -> None:
    result = classify(_entered(variable, entered), 0, RULES)

    by_variable = {condition.variable: condition for condition in result.conditions}
    assert by_variable[variable].band_level is expected
    assert by_variable[variable].level is expected


WORKED_EXAMPLES = [
    (20, 0, 0, 45000, LOW, None),
    (38, 0, 0, 40000, HIGH, "band:wind_speed"),
    (38, 0, 0, 40001, SEVERE, "load_rule:wind_speed"),
    (50, 0, 0, 30001, NO_TRAVEL, "load_rule:wind_speed"),
    (10, 1.00, 0, 0, SEVERE, "band:rain_rate"),
    (10, 1.00, 0, 80000, SEVERE, "band:rain_rate"),
    (10, 0.30, 2.5, 0, SEVERE, "band:snowfall_rate"),
    (10, 0.30, 2.5, 80000, SEVERE, "band:snowfall_rate"),
]


@pytest.mark.parametrize(
    ("wind_mph", "rain_in_h", "snow_in_h", "load_lb", "expected", "expected_decided_by"),
    WORKED_EXAMPLES,
)
def test_worked_examples(  # noqa: PLR0913, PLR0917
    wind_mph: float,
    rain_in_h: float,
    snow_in_h: float,
    load_lb: float,
    expected: RiskLevel,
    expected_decided_by: str | None,
) -> None:
    result = classify(_values(wind_mph, rain_in_h, snow_in_h), _kg(load_lb), RULES)

    assert result.level is expected
    assert result.decided_by == expected_decided_by


@pytest.mark.parametrize(
    ("wind_mph", "rain_in_h", "snow_in_h", "load_lb", "expected", "expected_decided_by"),
    WORKED_EXAMPLES,
)
def test_worked_examples_through_the_validator(  # noqa: PLR0913, PLR0917
    wind_mph: float,
    rain_in_h: float,
    snow_in_h: float,
    load_lb: float,
    expected: RiskLevel,
    expected_decided_by: str | None,
) -> None:
    rules = validate_rule_set(default_rule_set_document())

    result = classify(_values(wind_mph, rain_in_h, snow_in_h), _kg(load_lb), rules)

    assert result.level is expected
    assert result.decided_by == expected_decided_by


LOAD_RULE_CASES = [
    (38, 40000, HIGH, "band:wind_speed"),
    (38, 40000.01, SEVERE, "load_rule:wind_speed"),
    (38, 39999, HIGH, "band:wind_speed"),
    (34.99, 80000, MODERATE, "band:wind_speed"),
    (35, 40000, HIGH, "band:wind_speed"),
    (35, 40001, SEVERE, "load_rule:wind_speed"),
    (44.99, 40001, SEVERE, "load_rule:wind_speed"),
    (45, 30000, SEVERE, "band:wind_speed"),
    (45, 30001, NO_TRAVEL, "load_rule:wind_speed"),
    (45, 30000.01, NO_TRAVEL, "load_rule:wind_speed"),
    (54.99, 30001, NO_TRAVEL, "load_rule:wind_speed"),
    (55, 0, NO_TRAVEL, "band:wind_speed"),
    (55, 80000, NO_TRAVEL, "band:wind_speed"),
]


@pytest.mark.parametrize(
    ("wind_mph", "load_lb", "expected", "expected_decided_by"), LOAD_RULE_CASES
)
def test_load_rules_at_weight_and_range_ends(
    wind_mph: float, load_lb: float, expected: RiskLevel, expected_decided_by: str
) -> None:
    result = classify(_values(wind_mph=wind_mph), _kg(load_lb), RULES)

    assert result.level is expected
    assert result.decided_by == expected_decided_by


def test_load_rule_raises_the_condition_level() -> None:
    result = classify(_values(wind_mph=38), _kg(40001), RULES)

    wind = result.conditions[0]
    assert (wind.band_level, wind.level) == (HIGH, SEVERE)


def test_load_rule_never_lowers_a_level() -> None:
    lowering = _rule_set(load_rules=((WIND, MPH, 45, 60, 1000, MODERATE),))

    result = classify(_values(wind_mph=56), _kg(80000), lowering)

    assert result.level is NO_TRAVEL
    assert result.decided_by == "band:wind_speed"
    assert result.conditions[0].level is NO_TRAVEL


def test_worst_of_conditions_wins() -> None:
    result = classify(_values(wind_mph=30, rain_in_h=0.3, snow_in_h=2.1), 0, RULES)

    assert result.level is SEVERE
    assert result.decided_by == "band:snowfall_rate"
    assert [condition.level for condition in result.conditions] == [MODERATE, HIGH, SEVERE]


def test_tie_reports_the_first_condition_in_rule_set_order() -> None:
    result = classify(_values(wind_mph=45, rain_in_h=0.5, snow_in_h=2.0), 0, RULES)

    assert result.level is SEVERE
    assert result.decided_by == "band:wind_speed"


def test_tie_between_a_band_and_a_load_rule_reports_the_band() -> None:
    result = classify(_values(wind_mph=38, rain_in_h=0.5), _kg(40001), RULES)

    assert result.level is SEVERE
    assert result.decided_by == "band:rain_rate"


@pytest.mark.parametrize("missing", [WIND, RAIN, SNOW])
def test_missing_variable_is_unknown_never_low(missing: WeatherVariable) -> None:
    values = _values()
    values[missing] = None

    result = classify(values, 0, RULES)

    assert result == Classification(
        level=None,
        decided_by=None,
        conditions=tuple(
            ConditionLevel(variable, None, None, None)
            if variable is missing
            else ConditionLevel(variable, 0.0, LOW, LOW)
            for variable in DEFAULT_BANDS
        ),
    )


def test_absent_variable_is_unknown_even_when_another_is_extreme() -> None:
    values = _values(wind_mph=80)
    del values[SNOW]

    result = classify(values, 0, RULES)

    assert result.level is None
    assert result.conditions[0].level is NO_TRAVEL


def test_variable_used_only_by_a_load_rule_must_be_present() -> None:
    rules = replace(RULES, conditions=RULES.conditions[1:])
    values = _values()
    values[WIND] = None

    assert rule_set_variables(rules) == (RAIN, SNOW, WIND)
    assert classify(values, 0, rules).level is None


def test_rule_set_variables_in_order_without_repeats() -> None:
    assert rule_set_variables(RULES) == (WIND, RAIN, SNOW)
