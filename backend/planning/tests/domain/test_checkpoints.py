import pytest

from planning.constants import KM_PER_DEGREE
from planning.domain.checkpoints import (
    TooManyCheckpoints,
    checkpoint_count,
    checkpoint_distances_km,
    place_checkpoints,
    place_samples,
)
from planning.domain.geometry import measure_line
from planning.domain.values import Coordinate
from planning.errors import ErrorCode

SPACING_KM = 40.0


def _equator_line(count: int, step_deg: float) -> tuple[Coordinate, ...]:
    return tuple(Coordinate(latitude=0.0, longitude=index * step_deg) for index in range(count))


@pytest.mark.parametrize(
    ("length_km", "expected"),
    [
        (0.0, (0.0, 0.0)),
        (25.0, (0.0, 25.0)),
        (40.0, (0.0, 40.0)),
        (120.0, (0.0, 40.0, 80.0, 120.0)),
        (129.9, (0.0, 40.0, 80.0, 129.9)),
        (130.0, (0.0, 40.0, 80.0, 120.0, 130.0)),
        (130.1, (0.0, 40.0, 80.0, 120.0, 130.1)),
        (45.0, (0.0, 45.0)),
        (50.0, (0.0, 40.0, 50.0)),
    ],
)
def test_checkpoint_distances(length_km: float, expected: tuple[float, ...]) -> None:
    assert checkpoint_distances_km(length_km, SPACING_KM) == pytest.approx(expected)
    assert checkpoint_count(length_km, SPACING_KM) == len(expected)


@pytest.mark.parametrize("length_km", [0.0, 1.0, 39.9, 40.0, 40.1, 99.99, 100.0, 1234.5, 3000.0])
@pytest.mark.parametrize("spacing_km", [16.09344, 40.2336, 80.4672])
def test_count_matches_distances(length_km: float, spacing_km: float) -> None:
    distances = checkpoint_distances_km(length_km, spacing_km)
    assert checkpoint_count(length_km, spacing_km) == len(distances)
    assert distances[0] == 0.0
    assert distances[-1] == length_km
    assert list(distances) == sorted(distances)


def test_origin_and_destination_always_present() -> None:
    points = _equator_line(11, step_deg=0.1)
    line = measure_line(points)
    checkpoints = place_checkpoints(line, spacing_km=500.0, max_count=10)
    assert [checkpoint.index for checkpoint in checkpoints] == [0, 1]
    assert checkpoints[0].coordinate == points[0]
    assert checkpoints[-1].coordinate == points[-1]
    assert checkpoints[-1].distance_km == pytest.approx(line.length_km)


def test_positions_interpolated_on_a_known_line() -> None:
    line = measure_line(
        (
            Coordinate(latitude=0.0, longitude=0.0),
            Coordinate(latitude=0.0, longitude=1.0),
            Coordinate(latitude=1.0, longitude=1.0),
        )
    )
    checkpoints = place_checkpoints(line, spacing_km=KM_PER_DEGREE / 2, max_count=10)
    coordinates = [
        (checkpoint.coordinate.latitude, checkpoint.coordinate.longitude)
        for checkpoint in checkpoints
    ]
    assert coordinates == [
        pytest.approx((0.0, 0.0)),
        pytest.approx((0.0, 0.5)),
        pytest.approx((0.0, 1.0)),
        pytest.approx((0.5, 1.0)),
        pytest.approx((1.0, 1.0)),
    ]


def test_cap_reached_is_allowed() -> None:
    line = measure_line(_equator_line(2, step_deg=1.0))
    count = checkpoint_count(line.length_km, 10.0)
    assert len(place_checkpoints(line, spacing_km=10.0, max_count=count)) == count


def test_cap_exceeded_is_rejected() -> None:
    line = measure_line(_equator_line(2, step_deg=1.0))
    count = checkpoint_count(line.length_km, 10.0)
    with pytest.raises(TooManyCheckpoints) as caught:
        place_checkpoints(line, spacing_km=10.0, max_count=count - 1)
    assert caught.value.count == count
    assert caught.value.cap == count - 1
    assert caught.value.code is ErrorCode.INVALID_REQUEST


def test_cap_is_checked_before_building_a_huge_list() -> None:
    line = measure_line(_equator_line(2, step_deg=10.0))
    with pytest.raises(TooManyCheckpoints):
        place_checkpoints(line, spacing_km=1e-6, max_count=200)


def test_place_samples_keeps_order_and_clamps() -> None:
    line = measure_line(_equator_line(3, step_deg=1.0))
    samples = place_samples(line, (1.5 * KM_PER_DEGREE, 0.25 * KM_PER_DEGREE, 99999.0))
    assert [sample.coordinate.longitude for sample in samples] == pytest.approx([1.5, 0.25, 2.0])
    assert samples[0].distance_km == pytest.approx(1.5 * KM_PER_DEGREE)
