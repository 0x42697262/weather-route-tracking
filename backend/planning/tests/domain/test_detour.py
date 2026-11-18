import pytest

from planning.constants import DETOUR_MAX_OFFSET_KM, DETOUR_MIN_OFFSET_KM, DETOUR_OFFSET_ROUTE_SHARE
from planning.domain.detour import detour_offset_km, detour_vias
from planning.domain.geometry import haversine_km, measure_line, point_at_km
from planning.domain.values import Coordinate


def _eastbound(length_deg: float) -> tuple[Coordinate, ...]:
    count = 101
    return tuple(
        Coordinate(latitude=0.0, longitude=index * length_deg / (count - 1))
        for index in range(count)
    )


@pytest.mark.parametrize(
    ("length_km", "expected_km"),
    [
        (0.0, DETOUR_MIN_OFFSET_KM),
        (10.0, DETOUR_MIN_OFFSET_KM),
        (100.0, 100.0 * DETOUR_OFFSET_ROUTE_SHARE),
        (2000.0, DETOUR_MAX_OFFSET_KM),
    ],
)
def test_offset_is_a_clamped_share_of_the_length(length_km: float, expected_km: float) -> None:
    assert detour_offset_km(length_km) == pytest.approx(expected_km)


def test_vias_go_left_then_right_from_the_middle() -> None:
    line = measure_line(_eastbound(2.0))
    left, right = detour_vias(line)
    middle = point_at_km(line, line.length_km / 2)
    expected_km = detour_offset_km(line.length_km)
    assert left.latitude > 0
    assert right.latitude < 0
    for via in (left, right):
        assert via.longitude == pytest.approx(1.0, abs=1e-6)
        assert haversine_km(middle, via) == pytest.approx(expected_km)


def test_line_without_length_has_no_vias() -> None:
    point = Coordinate(latitude=1.0, longitude=1.0)
    assert detour_vias(measure_line((point, point))) == ()
