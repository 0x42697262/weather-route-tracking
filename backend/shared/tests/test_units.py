import pytest

from shared.units import (
    METRIC_UNIT_BY_DIMENSION,
    UNITS,
    Dimension,
    IncompatibleUnitsError,
    Unit,
    convert,
    units_of,
)


@pytest.mark.parametrize(
    ("value", "from_unit", "to_unit", "expected"),
    [
        (1, Unit.MILES_PER_HOUR, Unit.KILOMETERS_PER_HOUR, 1.609344),
        (25, Unit.MILES_PER_HOUR, Unit.KILOMETERS_PER_HOUR, 40.2336),
        (55, Unit.MILES_PER_HOUR, Unit.KILOMETERS_PER_HOUR, 88.51392),
        (1, Unit.METERS_PER_SECOND, Unit.KILOMETERS_PER_HOUR, 3.6),
        (1, Unit.KNOTS, Unit.KILOMETERS_PER_HOUR, 1.852),
        (1, Unit.MILES, Unit.KILOMETERS, 1.609344),
        (1000, Unit.METERS, Unit.KILOMETERS, 1),
        (1, Unit.INCHES_PER_HOUR, Unit.MILLIMETERS_PER_HOUR, 25.4),
        (1, Unit.INCHES_PER_HOUR, Unit.CENTIMETERS_PER_HOUR, 2.54),
        (1, Unit.CENTIMETERS_PER_HOUR, Unit.MILLIMETERS_PER_HOUR, 10),
        (3, Unit.INCHES_PER_HOUR, Unit.CENTIMETERS_PER_HOUR, 7.62),
        (1, Unit.POUNDS, Unit.KILOGRAMS, 0.45359237),
        (30000, Unit.POUNDS, Unit.KILOGRAMS, 13607.7711),
        (1, Unit.METRIC_TONS, Unit.KILOGRAMS, 1000),
        (1.609344, Unit.KILOMETERS, Unit.MILES, 1),
    ],
)
def test_conversion_uses_exact_factor(
    value: float, from_unit: Unit, to_unit: Unit, expected: float
) -> None:
    assert convert(value, from_unit, to_unit) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("unit", list(Unit))
def test_round_trip_through_metric(unit: Unit) -> None:
    metric = METRIC_UNIT_BY_DIMENSION[UNITS[unit].dimension]

    assert convert(convert(12.345, unit, metric), metric, unit) == pytest.approx(12.345)


@pytest.mark.parametrize("unit", list(Unit))
def test_same_unit_is_unchanged(unit: Unit) -> None:
    assert convert(7.25, unit, unit) == 7.25


def test_different_dimensions_are_rejected() -> None:
    with pytest.raises(IncompatibleUnitsError):
        convert(1, Unit.MILES, Unit.MILES_PER_HOUR)


def test_every_unit_has_a_dimension_with_a_metric_unit() -> None:
    assert set(METRIC_UNIT_BY_DIMENSION) == set(Dimension)
    for dimension, metric in METRIC_UNIT_BY_DIMENSION.items():
        assert metric in units_of(dimension)
        assert UNITS[metric].factor_to_base == 1
    assert set().union(*(units_of(dimension) for dimension in Dimension)) == set(Unit)
