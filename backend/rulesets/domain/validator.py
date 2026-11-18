"""The one way a rule set document becomes a `RuleSet` (`docs/rule-sets.md`).

Pure: no I/O, no Django. Every threshold is converted once to the metric unit of its variable;
weights to kg, speeds to km/h, distances to km and rest limits to seconds.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from rulesets import text
from rulesets.constants import (
    CURRENT_SCHEMA_VERSION,
    FIRST_SCHEMA_VERSION,
    KNOWN_SCHEMA_VERSIONS,
    MAX_BANDS_PER_CONDITION,
    MAX_CHECKPOINT_SPACINGS,
    MAX_CONDITIONS,
    MAX_EMPTY_VEHICLE_WEIGHT_KG,
    MAX_LOAD_RULES,
    MAX_TRUCK_MAX_SPEED_KMH,
    MAX_TRUCK_SPEED_FACTOR,
    MAX_UNKNOWN_SHARE,
    MIN_EMPTY_VEHICLE_WEIGHT_KG,
    MIN_TRUCK_MAX_SPEED_KMH,
    MIN_TRUCK_SPEED_FACTOR,
    MIN_UNKNOWN_SHARE,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
)
from rulesets.domain.schema import (
    Band,
    Condition,
    LoadRule,
    RestRules,
    RuleSet,
    Spacing,
    StretchMethod,
)
from rulesets.domain.spacings import find_spacing
from rulesets.keys import ROOT_FIELD, Key, child_field, item_field
from shared.risk_levels import LOWEST_LEVEL, RISK_LEVELS, RiskLevel
from shared.units import METRIC_UNIT_BY_DIMENSION, UNITS, Dimension, Unit, convert, units_of
from shared.weather_variables import WEATHER_VARIABLES, WeatherVariable


class _Missing:
    """Marks a key that is absent; its problem is already reported."""


_MISSING: Final = _Missing()

FIRST_DOCUMENT_KEYS: Final = frozenset(
    {
        Key.SCHEMA_VERSION,
        Key.CONDITIONS,
        Key.LOAD_RULES,
        Key.TRUCK_SPEED_FACTOR,
        Key.TRUCK_MAX_SPEED,
        Key.EMPTY_VEHICLE_WEIGHT,
        Key.REST_RULES,
        Key.STRETCH_METHOD,
        Key.FERRY_LEVEL,
        Key.CHECKPOINT_SPACINGS,
        Key.DEFAULT_CHECKPOINT_SPACING,
    }
)
DOCUMENT_KEYS_BY_SCHEMA_VERSION: Final[Mapping[int, frozenset[Key]]] = MappingProxyType(
    {
        FIRST_SCHEMA_VERSION: FIRST_DOCUMENT_KEYS,
        CURRENT_SCHEMA_VERSION: FIRST_DOCUMENT_KEYS | {Key.MAX_UNKNOWN_SHARE},
    },
)
DOCUMENT_KEYS: Final = DOCUMENT_KEYS_BY_SCHEMA_VERSION[CURRENT_SCHEMA_VERSION]
CONDITION_KEYS: Final = frozenset({Key.VARIABLE, Key.UNIT, Key.BANDS})
BAND_KEYS: Final = frozenset({Key.LEVEL, Key.FROM, Key.INCLUSIVE})
LOAD_RULE_KEYS: Final = frozenset(
    {Key.VARIABLE, Key.UNIT, Key.FROM, Key.TO, Key.LOAD_OVER, Key.LEVEL}
)
QUANTITY_KEYS: Final = frozenset({Key.VALUE, Key.UNIT})
REST_RULE_KEYS: Final = frozenset(
    {
        Key.ENABLED,
        Key.MAX_DRIVING_BEFORE_BREAK_HOURS,
        Key.BREAK_MINUTES,
        Key.MAX_DRIVING_PER_SHIFT_HOURS,
        Key.MAX_SHIFT_HOURS,
        Key.OFF_DUTY_HOURS,
    }
)

SPEED_UNIT: Final = METRIC_UNIT_BY_DIMENSION[Dimension.SPEED]
MASS_UNIT: Final = METRIC_UNIT_BY_DIMENSION[Dimension.MASS]
DISTANCE_UNIT: Final = METRIC_UNIT_BY_DIMENSION[Dimension.DISTANCE]


@dataclass(frozen=True, slots=True)
class RuleSetProblem:
    """One problem: where it is (a JSON-path-like field, `$` for the root) and what is wrong."""

    field: str
    message: str


class RuleSetInvalid(Exception):
    """The document is not a valid rule set. `problems` lists every problem found."""

    def __init__(self, problems: tuple[RuleSetProblem, ...]) -> None:
        """Keep every problem."""
        super().__init__(text.rule_set_invalid(len(problems)))
        self.problems = problems


class _ReaderInvariantError(RuntimeError):
    """A reader returned no value without reporting a problem."""


class _Problems:
    """Collects problems while the document is read."""

    __slots__ = ("items",)

    def __init__(self) -> None:
        self.items: list[RuleSetProblem] = []

    def add(self, field: str, message: str) -> None:
        self.items.append(RuleSetProblem(field=field, message=message))


@dataclass(frozen=True, slots=True)
class _Quantity:
    value: float
    unit: Unit


@dataclass(frozen=True, slots=True)
class _RawBand:
    level: RiskLevel
    from_value: float
    inclusive: bool


@dataclass(frozen=True, slots=True)
class _RawLoadRule:
    from_value: float
    to_value: float


def _known[T](value: T | None) -> T:
    if value is None:
        raise _ReaderInvariantError
    return value


def _get(document: Mapping[str, object], key: str) -> object:
    return document.get(key, _MISSING)


def _read_object(
    value: object, field: str, keys: frozenset[Key], problems: _Problems
) -> Mapping[str, object] | None:
    if value is _MISSING:
        return None
    if not isinstance(value, dict):
        problems.add(field, text.NOT_AN_OBJECT)
        return None
    present = {str(key) for key in value}
    for missing_key in sorted(keys - present):
        problems.add(child_field(field, missing_key), text.MISSING_KEY)
    for extra_key in sorted(present - keys):
        problems.add(child_field(field, extra_key), text.UNKNOWN_KEY)
    return {str(key): item for key, item in value.items()}


def _read_list(value: object, field: str, maximum: int, problems: _Problems) -> list[object] | None:
    if value is _MISSING:
        return None
    if not isinstance(value, list):
        problems.add(field, text.NOT_A_LIST)
        return None
    if not value:
        problems.add(field, text.MUST_NOT_BE_EMPTY)
    if len(value) > maximum:
        problems.add(field, text.too_many(maximum))
    return list(value)


def _read_number(value: object, field: str, problems: _Problems) -> float | None:
    if value is _MISSING:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        problems.add(field, text.NOT_A_NUMBER)
        return None
    try:
        number = float(value)
    except OverflowError:
        number = math.inf
    if not math.isfinite(number):
        problems.add(field, text.NOT_A_NUMBER)
        return None
    return number


def _read_positive(value: object, field: str, problems: _Problems) -> float | None:
    number = _read_number(value, field, problems)
    if number is not None and number <= 0:
        problems.add(field, text.MUST_BE_POSITIVE)
        return None
    return number


def _read_bool(value: object, field: str, problems: _Problems) -> bool | None:
    if value is _MISSING:
        return None
    if not isinstance(value, bool):
        problems.add(field, text.NOT_A_BOOLEAN)
        return None
    return value


def _read_choice[Choice: StrEnum](
    value: object, field: str, choices: type[Choice], problems: _Problems
) -> Choice | None:
    if value is _MISSING:
        return None
    allowed = {choice.value for choice in choices}
    if not isinstance(value, str) or value not in allowed:
        problems.add(field, text.not_one_of(allowed))
        return None
    return choices(value)


def _read_unit(
    value: object, field: str, allowed: frozenset[Unit], problems: _Problems
) -> Unit | None:
    if value is _MISSING:
        return None
    if not isinstance(value, str) or value not in allowed:
        problems.add(field, text.not_one_of(allowed))
        return None
    return Unit(value)


def _read_level(value: object, field: str, problems: _Problems) -> RiskLevel | None:
    return _read_choice(value, field, RiskLevel, problems)


def _read_quantity(
    value: object, field: str, dimension: Dimension, problems: _Problems
) -> _Quantity | None:
    document = _read_object(value, field, QUANTITY_KEYS, problems)
    if document is None:
        return None
    amount = _read_positive(_get(document, Key.VALUE), child_field(field, Key.VALUE), problems)
    unit = _read_unit(
        _get(document, Key.UNIT), child_field(field, Key.UNIT), units_of(dimension), problems
    )
    if amount is None or unit is None:
        return None
    return _Quantity(value=amount, unit=unit)


def _in_metric(
    quantity: _Quantity | None,
    field: str,
    bounds: tuple[float, float],
    problems: _Problems,
) -> float | None:
    if quantity is None:
        return None
    metric_unit = METRIC_UNIT_BY_DIMENSION[UNITS[quantity.unit].dimension]
    metric = convert(quantity.value, quantity.unit, metric_unit)
    minimum, maximum = bounds
    if not minimum <= metric <= maximum:
        problems.add(field, text.out_of_bounds_in_unit(minimum, maximum, metric_unit.value))
        return None
    return metric


def _read_band(value: object, field: str, problems: _Problems) -> _RawBand | None:
    document = _read_object(value, field, BAND_KEYS, problems)
    if document is None:
        return None
    level_field = child_field(field, Key.LEVEL)
    level = _read_level(_get(document, Key.LEVEL), level_field, problems)
    if level is LOWEST_LEVEL:
        problems.add(level_field, text.LOW_BAND)
        level = None
    from_value = _read_number(_get(document, Key.FROM), child_field(field, Key.FROM), problems)
    inclusive = _read_bool(
        _get(document, Key.INCLUSIVE), child_field(field, Key.INCLUSIVE), problems
    )
    if level is None or from_value is None or inclusive is None:
        return None
    return _RawBand(level=level, from_value=from_value, inclusive=inclusive)


def _read_bands(value: object, field: str, problems: _Problems) -> tuple[_RawBand, ...]:
    items = _read_list(value, field, MAX_BANDS_PER_CONDITION, problems)
    if items is None:
        return ()
    bands: list[_RawBand] = []
    for index, item in enumerate(items):
        band_field = item_field(field, index)
        band = _read_band(item, band_field, problems)
        if band is None:
            continue
        if bands and band.from_value <= bands[-1].from_value:
            problems.add(child_field(band_field, Key.FROM), text.BAND_BOUND_NOT_ASCENDING)
        if bands and RISK_LEVELS[band.level].score <= RISK_LEVELS[bands[-1].level].score:
            problems.add(child_field(band_field, Key.LEVEL), text.BAND_LEVEL_NOT_ASCENDING)
        bands.append(band)
    return tuple(bands)


def _read_variable_and_unit(
    document: Mapping[str, object], field: str, problems: _Problems
) -> tuple[WeatherVariable | None, Unit | None]:
    variable = _read_choice(
        _get(document, Key.VARIABLE), child_field(field, Key.VARIABLE), WeatherVariable, problems
    )
    if variable is None:
        return None, None
    unit = _read_unit(
        _get(document, Key.UNIT),
        child_field(field, Key.UNIT),
        WEATHER_VARIABLES[variable].allowed_units,
        problems,
    )
    return variable, unit


def _to_variable_unit(value: float, unit: Unit, variable: WeatherVariable) -> float:
    return convert(value, unit, WEATHER_VARIABLES[variable].metric_unit)


def _read_condition(value: object, field: str, problems: _Problems) -> Condition | None:
    document = _read_object(value, field, CONDITION_KEYS, problems)
    if document is None:
        return None
    variable, unit = _read_variable_and_unit(document, field, problems)
    bands = _read_bands(_get(document, Key.BANDS), child_field(field, Key.BANDS), problems)
    if variable is None or unit is None:
        return None
    return Condition(
        variable=variable,
        bands=tuple(
            Band(
                level=band.level,
                from_value=_to_variable_unit(band.from_value, unit, variable),
                inclusive=band.inclusive,
            )
            for band in bands
        ),
    )


def _read_conditions(value: object, field: str, problems: _Problems) -> tuple[Condition, ...]:
    items = _read_list(value, field, MAX_CONDITIONS, problems)
    if items is None:
        return ()
    conditions: list[Condition] = []
    for index, item in enumerate(items):
        condition_field = item_field(field, index)
        condition = _read_condition(item, condition_field, problems)
        if condition is None:
            continue
        if any(seen.variable is condition.variable for seen in conditions):
            problems.add(child_field(condition_field, Key.VARIABLE), text.DUPLICATE_VARIABLE)
        conditions.append(condition)
    return tuple(conditions)


def _read_load_range(
    document: Mapping[str, object], field: str, problems: _Problems
) -> _RawLoadRule | None:
    from_value = _read_number(_get(document, Key.FROM), child_field(field, Key.FROM), problems)
    to_value = _read_number(_get(document, Key.TO), child_field(field, Key.TO), problems)
    if from_value is None or to_value is None:
        return None
    if from_value >= to_value:
        problems.add(child_field(field, Key.FROM), text.LOAD_RULE_RANGE_EMPTY)
        return None
    return _RawLoadRule(from_value=from_value, to_value=to_value)


def _read_load_rule(value: object, field: str, problems: _Problems) -> LoadRule | None:
    document = _read_object(value, field, LOAD_RULE_KEYS, problems)
    if document is None:
        return None
    variable, unit = _read_variable_and_unit(document, field, problems)
    load_range = _read_load_range(document, field, problems)
    load_over = _read_quantity(
        _get(document, Key.LOAD_OVER), child_field(field, Key.LOAD_OVER), Dimension.MASS, problems
    )
    level = _read_level(_get(document, Key.LEVEL), child_field(field, Key.LEVEL), problems)
    if variable is None or unit is None or load_range is None or load_over is None:
        return None
    if level is None:
        return None
    return LoadRule(
        variable=variable,
        from_value=_to_variable_unit(load_range.from_value, unit, variable),
        to_value=_to_variable_unit(load_range.to_value, unit, variable),
        load_over_kg=convert(load_over.value, load_over.unit, MASS_UNIT),
        level=level,
    )


def _read_load_rules(value: object, field: str, problems: _Problems) -> tuple[LoadRule, ...]:
    items = _read_list_allow_empty(value, field, MAX_LOAD_RULES, problems)
    rules = (
        _read_load_rule(item, item_field(field, index), problems)
        for index, item in enumerate(items)
    )
    return tuple(rule for rule in rules if rule is not None)


def _read_list_allow_empty(
    value: object, field: str, maximum: int, problems: _Problems
) -> list[object]:
    if value is _MISSING:
        return []
    if not isinstance(value, list):
        problems.add(field, text.NOT_A_LIST)
        return []
    if len(value) > maximum:
        problems.add(field, text.too_many(maximum))
    return list(value)


def _read_speed_factor(value: object, field: str, problems: _Problems) -> float | None:
    factor = _read_number(value, field, problems)
    if factor is None:
        return None
    if not MIN_TRUCK_SPEED_FACTOR <= factor <= MAX_TRUCK_SPEED_FACTOR:
        problems.add(field, text.out_of_bounds(MIN_TRUCK_SPEED_FACTOR, MAX_TRUCK_SPEED_FACTOR))
        return None
    return factor


def _read_max_unknown_share(value: object, field: str, problems: _Problems) -> float | None:
    if value is None:
        return None
    share = _read_number(value, field, problems)
    if share is None:
        return None
    if not MIN_UNKNOWN_SHARE <= share <= MAX_UNKNOWN_SHARE:
        problems.add(field, text.out_of_bounds(MIN_UNKNOWN_SHARE, MAX_UNKNOWN_SHARE))
        return None
    return share


def _read_max_speed(value: object, field: str, problems: _Problems) -> float | None:
    quantity = _read_quantity(value, field, Dimension.SPEED, problems)
    return _in_metric(quantity, field, (MIN_TRUCK_MAX_SPEED_KMH, MAX_TRUCK_MAX_SPEED_KMH), problems)


def _read_empty_weight(value: object, field: str, problems: _Problems) -> float | None:
    quantity = _read_quantity(value, field, Dimension.MASS, problems)
    return _in_metric(
        quantity, field, (MIN_EMPTY_VEHICLE_WEIGHT_KG, MAX_EMPTY_VEHICLE_WEIGHT_KG), problems
    )


def _read_rest_rules(value: object, field: str, problems: _Problems) -> RestRules | None:
    document = _read_object(value, field, REST_RULE_KEYS, problems)
    if document is None:
        return None

    def positive(key: Key) -> float | None:
        return _read_positive(_get(document, key), child_field(field, key), problems)

    enabled = _read_bool(_get(document, Key.ENABLED), child_field(field, Key.ENABLED), problems)
    before_break_h = positive(Key.MAX_DRIVING_BEFORE_BREAK_HOURS)
    break_min = positive(Key.BREAK_MINUTES)
    per_shift_h = positive(Key.MAX_DRIVING_PER_SHIFT_HOURS)
    shift_h = positive(Key.MAX_SHIFT_HOURS)
    off_duty_h = positive(Key.OFF_DUTY_HOURS)
    if before_break_h is not None and per_shift_h is not None and before_break_h > per_shift_h:
        problems.add(
            child_field(field, Key.MAX_DRIVING_BEFORE_BREAK_HOURS),
            text.BREAK_LIMIT_ABOVE_SHIFT_DRIVING,
        )
    if per_shift_h is not None and shift_h is not None and per_shift_h > shift_h:
        problems.add(
            child_field(field, Key.MAX_DRIVING_PER_SHIFT_HOURS),
            text.SHIFT_DRIVING_ABOVE_SHIFT_LENGTH,
        )
    if enabled is None or before_break_h is None or break_min is None or per_shift_h is None:
        return None
    if shift_h is None or off_duty_h is None:
        return None
    return RestRules(
        enabled=enabled,
        max_driving_before_break_s=before_break_h * SECONDS_PER_HOUR,
        break_s=break_min * SECONDS_PER_MINUTE,
        max_driving_per_shift_s=per_shift_h * SECONDS_PER_HOUR,
        max_shift_s=shift_h * SECONDS_PER_HOUR,
        off_duty_s=off_duty_h * SECONDS_PER_HOUR,
    )


def _read_ferry_level(value: object, field: str, problems: _Problems) -> RiskLevel | None:
    if value is None:
        return None
    return _read_level(value, field, problems)


def _read_spacing(value: object, field: str, problems: _Problems) -> Spacing | None:
    quantity = _read_quantity(value, field, Dimension.DISTANCE, problems)
    if quantity is None:
        return None
    return Spacing(
        value=quantity.value,
        unit=quantity.unit,
        km=convert(quantity.value, quantity.unit, DISTANCE_UNIT),
    )


def _read_spacings(value: object, field: str, problems: _Problems) -> tuple[Spacing, ...]:
    items = _read_list(value, field, MAX_CHECKPOINT_SPACINGS, problems)
    if items is None:
        return ()
    spacings: list[Spacing] = []
    for index, item in enumerate(items):
        spacing_field = item_field(field, index)
        spacing = _read_spacing(item, spacing_field, problems)
        if spacing is None:
            continue
        if find_spacing(spacings, spacing.km) is not None:
            problems.add(spacing_field, text.DUPLICATE_SPACING)
        spacings.append(spacing)
    return tuple(spacings)


def _read_default_spacing(
    value: object, field: str, spacings: tuple[Spacing, ...], problems: _Problems
) -> Spacing | None:
    spacing = _read_spacing(value, field, problems)
    if spacing is None:
        return None
    allowed = find_spacing(spacings, spacing.km)
    if allowed is None:
        problems.add(field, text.DEFAULT_SPACING_NOT_ALLOWED)
    return allowed


def _check_schema_version(document: Mapping[str, object]) -> None:
    version = document.get(Key.SCHEMA_VERSION)
    is_integer = isinstance(version, int) and not isinstance(version, bool)
    if not is_integer or version not in KNOWN_SCHEMA_VERSIONS:
        problem = RuleSetProblem(
            field=child_field(ROOT_FIELD, Key.SCHEMA_VERSION),
            message=text.unknown_schema_version(KNOWN_SCHEMA_VERSIONS),
        )
        raise RuleSetInvalid((problem,))


def validate_rule_set(data: object) -> RuleSet:
    """Turn a rule set document into a metric `RuleSet`.

    Raises:
        RuleSetInvalid: with every problem found. An unknown `schema_version` is reported alone,
            because the rest of the document cannot be read without it.
    """
    if not isinstance(data, dict):
        raise RuleSetInvalid((RuleSetProblem(field=ROOT_FIELD, message=text.NOT_AN_OBJECT),))
    _check_schema_version(data)
    problems = _Problems()
    schema_version = data[Key.SCHEMA_VERSION]
    document_keys = DOCUMENT_KEYS_BY_SCHEMA_VERSION[schema_version]
    document = _known(_read_object(data, ROOT_FIELD, document_keys, problems))

    def field(key: Key) -> str:
        return child_field(ROOT_FIELD, key)

    def value(key: Key) -> object:
        return _get(document, key)

    conditions = _read_conditions(value(Key.CONDITIONS), field(Key.CONDITIONS), problems)
    load_rules = _read_load_rules(value(Key.LOAD_RULES), field(Key.LOAD_RULES), problems)
    speed_factor = _read_speed_factor(
        value(Key.TRUCK_SPEED_FACTOR), field(Key.TRUCK_SPEED_FACTOR), problems
    )
    max_speed_value = value(Key.TRUCK_MAX_SPEED)
    max_speed_kmh = (
        None
        if max_speed_value is None
        else _read_max_speed(max_speed_value, field(Key.TRUCK_MAX_SPEED), problems)
    )
    empty_weight_kg = _read_empty_weight(
        value(Key.EMPTY_VEHICLE_WEIGHT), field(Key.EMPTY_VEHICLE_WEIGHT), problems
    )
    rest_rules = _read_rest_rules(value(Key.REST_RULES), field(Key.REST_RULES), problems)
    stretch_method = _read_choice(
        value(Key.STRETCH_METHOD), field(Key.STRETCH_METHOD), StretchMethod, problems
    )
    ferry_level = _read_ferry_level(value(Key.FERRY_LEVEL), field(Key.FERRY_LEVEL), problems)
    max_unknown_share = (
        _read_max_unknown_share(
            value(Key.MAX_UNKNOWN_SHARE), field(Key.MAX_UNKNOWN_SHARE), problems
        )
        if Key.MAX_UNKNOWN_SHARE in document_keys
        else None
    )
    spacings = _read_spacings(
        value(Key.CHECKPOINT_SPACINGS), field(Key.CHECKPOINT_SPACINGS), problems
    )
    default_spacing = _read_default_spacing(
        value(Key.DEFAULT_CHECKPOINT_SPACING),
        field(Key.DEFAULT_CHECKPOINT_SPACING),
        spacings,
        problems,
    )
    if problems.items:
        raise RuleSetInvalid(tuple(problems.items))
    return RuleSet(
        conditions=conditions,
        load_rules=load_rules,
        truck_speed_factor=_known(speed_factor),
        truck_max_speed_kmh=max_speed_kmh,
        empty_vehicle_weight_kg=_known(empty_weight_kg),
        rest_rules=_known(rest_rules),
        stretch_method=_known(stretch_method),
        ferry_level=ferry_level,
        max_unknown_share=max_unknown_share,
        checkpoint_spacings=spacings,
        default_checkpoint_spacing=_known(default_spacing),
    )
