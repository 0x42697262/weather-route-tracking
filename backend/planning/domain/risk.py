"""Classify weather values with a rule set: bands per condition, then load rules, worst of all
(`docs/risk-model.md` steps 1 to 3). The one classifier for checkpoints and heatmap cells."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from planning.domain.risk_constants import DECIDED_BY_SEPARATOR
from rulesets.domain.schema import Band, Condition, LoadRule, RuleSet
from shared.risk_levels import LOWEST_LEVEL, RiskLevel, score, worse
from shared.weather_variables import WeatherVariable

type WeatherValues = Mapping[WeatherVariable, float | None]


class DecisionKind(StrEnum):
    """What decided a level: a condition's band or a load rule."""

    BAND = "band"
    LOAD_RULE = "load_rule"


@dataclass(frozen=True, slots=True)
class ConditionLevel:
    """One condition's value and levels.

    Attributes:
        variable: the condition's variable.
        value: its metric value, or None when missing.
        band_level: the level from its bands alone, the lowest level below every band; None
            when the value is missing.
        level: the band level raised by every matching load rule on the same variable; None when
            the value is missing. Load rules on this variable see only this value and the load.
    """

    variable: WeatherVariable
    value: float | None
    band_level: RiskLevel | None
    level: RiskLevel | None


@dataclass(frozen=True, slots=True)
class Classification:
    """The combined result.

    Attributes:
        level: the worst matched level; None (Unknown) when any variable the rule set uses is
            missing.
        decided_by: `"band:<variable>"` or `"load_rule:<variable>"` of the band or rule that set
            the level; on a tie the first in rule set order (conditions, then load rules). None
            when the level is Unknown or nothing matched (the lowest level).
        conditions: one entry per rule set condition, in rule set order.
    """

    level: RiskLevel | None
    decided_by: str | None
    conditions: tuple[ConditionLevel, ...]


def decided_by(kind: DecisionKind, variable: WeatherVariable) -> str:
    """The `decided_by` text for a band or load rule on a variable."""
    return f"{kind}{DECIDED_BY_SEPARATOR}{variable}"


def rule_set_variables(rules: RuleSet) -> tuple[WeatherVariable, ...]:
    """Every variable the rule set reads, conditions first, in rule set order, without repeats."""
    ordered = [condition.variable for condition in rules.conditions]
    ordered.extend(rule.variable for rule in rules.load_rules)
    return tuple(dict.fromkeys(ordered))


def _reaches(value: float, band: Band) -> bool:
    return value > band.from_value or (band.inclusive and value == band.from_value)


def band_level(value: float, condition: Condition) -> RiskLevel | None:
    """The level of the highest band the value reaches; None when it reaches no band."""
    reached: RiskLevel | None = None
    for band in condition.bands:
        if _reaches(value, band):
            reached = band.level
    return reached


def load_rule_matches(value: float, load_kg: float, rule: LoadRule) -> bool:
    """`from_value <= value < to_value` and the load is strictly over the rule's weight."""
    return rule.from_value <= value < rule.to_value and load_kg > rule.load_over_kg


def _raise_by_load_rules(
    level: RiskLevel,
    value: float,
    variable: WeatherVariable,
    load_kg: float,
    rules: RuleSet,
) -> RiskLevel:
    result = level
    for rule in rules.load_rules:
        if rule.variable is variable and load_rule_matches(value, load_kg, rule):
            result = worse(result, rule.level)
    return result


def _condition_level(
    condition: Condition, values: WeatherValues, load_kg: float, rules: RuleSet
) -> ConditionLevel:
    value = values.get(condition.variable)
    if value is None:
        return ConditionLevel(condition.variable, None, None, None)
    from_bands = band_level(value, condition) or LOWEST_LEVEL
    return ConditionLevel(
        variable=condition.variable,
        value=value,
        band_level=from_bands,
        level=_raise_by_load_rules(from_bands, value, condition.variable, load_kg, rules),
    )


def _candidates(
    values: Mapping[WeatherVariable, float], load_kg: float, rules: RuleSet
) -> list[tuple[RiskLevel, str]]:
    candidates: list[tuple[RiskLevel, str]] = []
    for condition in rules.conditions:
        level = band_level(values[condition.variable], condition)
        if level is not None:
            candidates.append((level, decided_by(DecisionKind.BAND, condition.variable)))
    candidates.extend(
        (rule.level, decided_by(DecisionKind.LOAD_RULE, rule.variable))
        for rule in rules.load_rules
        if load_rule_matches(values[rule.variable], load_kg, rule)
    )
    return candidates


def _worst_first(candidates: list[tuple[RiskLevel, str]]) -> tuple[RiskLevel, str] | None:
    best: tuple[RiskLevel, str] | None = None
    for candidate in candidates:
        if best is None or score(candidate[0]) > score(best[0]):
            best = candidate
    return best


def _known_values(
    values: WeatherValues, variables: tuple[WeatherVariable, ...]
) -> dict[WeatherVariable, float] | None:
    known: dict[WeatherVariable, float] = {}
    for variable in variables:
        value = values.get(variable)
        if value is None:
            return None
        known[variable] = value
    return known


def classify(values: WeatherValues, load_kg: float, rules: RuleSet) -> Classification:
    """Classify metric weather values and a load with a rule set.

    Bands give each condition a level; matching load rules can only raise it; the result is the
    worst of all. A value below every band is the lowest level. Any variable the rule set uses
    being absent or None makes the level None (Unknown), never the lowest level.
    """
    conditions = tuple(
        _condition_level(condition, values, load_kg, rules) for condition in rules.conditions
    )
    known = _known_values(values, rule_set_variables(rules))
    if known is None:
        return Classification(level=None, decided_by=None, conditions=conditions)
    decision = _worst_first(_candidates(known, load_kg, rules))
    if decision is None:
        return Classification(level=LOWEST_LEVEL, decided_by=None, conditions=conditions)
    level, source = decision
    return Classification(level=level, decided_by=source, conditions=conditions)
