import pytest

from planning.domain.refine import merge_samples, midpoints_to_sample
from planning.domain.risk_constants import REFINE_MAX_DEPTH
from planning.domain.stretches import RouteSample, StretchKind, worse_end
from shared.risk_levels import RiskLevel
from shared.units import Unit, convert

LOW = RiskLevel.LOW
HIGH = RiskLevel.HIGH


def _miles(value: float) -> float:
    return convert(value, Unit.MILES, Unit.KILOMETERS)


def _samples(*points: tuple[float, RiskLevel | None]) -> tuple[RouteSample, ...]:
    return tuple(RouteSample(distance_km, level, None) for distance_km, level in points)


def test_midpoint_only_where_levels_differ() -> None:
    samples = _samples((0, LOW), (40, LOW), (80, HIGH), (120, HIGH))

    assert midpoints_to_sample(samples, 10) == (60,)


def test_unknown_next_to_known_is_refined_and_unknown_pairs_are_not() -> None:
    samples = _samples((0, LOW), (40, None), (80, None))

    assert midpoints_to_sample(samples, 10) == (20,)


@pytest.mark.parametrize(("length_km", "expected"), [(10, ()), (10.01, (5.005,))])
def test_stretch_must_be_longer_than_the_minimum(
    length_km: float, expected: tuple[float, ...]
) -> None:
    samples = _samples((0, LOW), (length_km, HIGH))

    assert midpoints_to_sample(samples, 10) == pytest.approx(expected)


def test_merge_orders_and_drops_duplicates() -> None:
    existing = _samples((0, LOW), (40, HIGH))
    new = (RouteSample(20, HIGH, None, refined=True), RouteSample(40, LOW, None, refined=True))

    merged = merge_samples(existing, new)

    assert [sample.distance_km for sample in merged] == [0, 20, 40]
    assert merged[1].refined is True
    assert merged[2] == existing[1]


def _refine(change_km: float, length_km: float, min_length_km: float) -> tuple[RouteSample, ...]:
    def level_at(distance_km: float) -> RiskLevel:
        return LOW if distance_km < change_km else HIGH

    samples = _samples((0, level_at(0)), (length_km, level_at(length_km)))
    for _ in range(REFINE_MAX_DEPTH):
        positions = midpoints_to_sample(samples, min_length_km)
        if not positions:
            break
        new = tuple(
            RouteSample(position, level_at(position), None, refined=True) for position in positions
        )
        samples = merge_samples(samples, new)
    return samples


@pytest.mark.parametrize("change_fraction", [0.01, 0.1, 0.33, 0.5, 0.51, 0.77, 0.99])
def test_change_in_50_miles_with_8_mile_minimum_costs_at_most_3_samples(
    change_fraction: float,
) -> None:
    length_km = _miles(50)
    min_length_km = _miles(8)

    samples = _refine(change_fraction * length_km, length_km, min_length_km)

    added = [sample for sample in samples if sample.refined]
    assert len(added) <= 3
    high_stretches = [
        stretch
        for stretch in worse_end(samples)
        if stretch.level is HIGH and stretch.kind is StretchKind.RATED
    ]
    high_km = sum(stretch.length_km for stretch in high_stretches)
    true_high_km = length_km * (1 - change_fraction)
    assert high_km - true_high_km <= min_length_km
