import itertools

import pytest

from planning.domain.stretches import (
    RouteSample,
    Stretch,
    StretchKind,
    build_stretches,
    is_on_ferry,
    merge_intervals,
    worse_end,
)
from rulesets.domain.schema import StretchMethod
from shared.risk_levels import RiskLevel

LOW = RiskLevel.LOW
MODERATE = RiskLevel.MODERATE
HIGH = RiskLevel.HIGH
SEVERE = RiskLevel.SEVERE
RATED = StretchKind.RATED
UNKNOWN = StretchKind.UNKNOWN
FERRY = StretchKind.FERRY


def _samples(*points: tuple[float, RiskLevel | None]) -> tuple[RouteSample, ...]:
    return tuple(RouteSample(distance_km, level, None) for distance_km, level in points)


@pytest.mark.parametrize("method", list(StretchMethod))
def test_worse_of_two_ends(method: StretchMethod) -> None:
    samples = _samples((0, LOW), (40, HIGH), (80, MODERATE), (120, MODERATE))

    assert build_stretches(samples, method, (), None) == (
        Stretch(0, 40, HIGH, RATED),
        Stretch(40, 80, HIGH, RATED),
        Stretch(80, 120, MODERATE, RATED),
    )


def test_unknown_end_makes_stretch_unknown() -> None:
    samples = _samples((0, SEVERE), (40, None), (80, LOW))

    assert worse_end(samples) == (Stretch(0, 40, None, UNKNOWN), Stretch(40, 80, None, UNKNOWN))


def test_samples_at_the_same_distance_give_no_stretch() -> None:
    samples = _samples((0, LOW), (0, HIGH), (10, LOW))

    assert worse_end(samples) == (Stretch(0, 10, HIGH, RATED),)


def test_one_sample_gives_no_stretch() -> None:
    assert worse_end(_samples((0, LOW))) == ()


def test_not_rated_ferry_splits_a_stretch() -> None:
    samples = _samples((0, HIGH), (40, LOW), (80, LOW))

    assert build_stretches(samples, StretchMethod.WORSE_END, ((30, 50),), None) == (
        Stretch(0, 30, HIGH, RATED),
        Stretch(30, 40, None, FERRY),
        Stretch(40, 50, None, FERRY),
        Stretch(50, 80, LOW, RATED),
    )


def test_ferry_with_a_level_takes_that_level() -> None:
    samples = _samples((0, LOW), (100, LOW))

    assert build_stretches(samples, StretchMethod.WORSE_END, ((20, 40), (60, 70)), SEVERE) == (
        Stretch(0, 20, LOW, RATED),
        Stretch(20, 40, SEVERE, FERRY),
        Stretch(40, 60, LOW, RATED),
        Stretch(60, 70, SEVERE, FERRY),
        Stretch(70, 100, LOW, RATED),
    )


def test_ferry_covering_a_whole_unknown_stretch_is_ferry() -> None:
    samples = _samples((0, LOW), (10, None), (20, None))

    assert build_stretches(samples, StretchMethod.WORSE_END, ((5, 25),), None) == (
        Stretch(0, 5, None, UNKNOWN),
        Stretch(5, 10, None, FERRY),
        Stretch(10, 20, None, FERRY),
    )


def test_ferry_outside_the_route_changes_nothing() -> None:
    samples = _samples((0, LOW), (10, HIGH))

    assert build_stretches(samples, StretchMethod.WORSE_END, ((20, 30),), None) == (
        Stretch(0, 10, HIGH, RATED),
    )


def test_merge_intervals_sorts_and_joins() -> None:
    assert merge_intervals(((50, 60), (10, 20), (15, 30), (30, 35), (70, 70))) == (
        (10, 35),
        (50, 60),
    )


@pytest.mark.parametrize(
    ("distance_km", "expected"),
    [(9.9, False), (10, True), (15, True), (20, True), (20.1, False)],
)
def test_checkpoint_on_a_ferry(distance_km: float, *, expected: bool) -> None:
    assert is_on_ferry(distance_km, ((10, 20),)) is expected


def test_stretches_cover_the_route() -> None:
    samples = _samples((0, LOW), (13.5, None), (27, HIGH), (40.2, SEVERE), (51.7, LOW))

    stretches = build_stretches(samples, StretchMethod.WORSE_END, ((20, 30), (45, 46)), None)

    assert stretches[0].start_km == 0
    assert stretches[-1].end_km == 51.7
    assert all(first.end_km == second.start_km for first, second in itertools.pairwise(stretches))
    assert sum(stretch.length_km for stretch in stretches) == pytest.approx(51.7)
