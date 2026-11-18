import itertools
import math

import pytest

from planning.constants import KM_PER_DEGREE
from planning.domain.geometry import (
    DegenerateLine,
    KmInterval,
    PolylineInvalid,
    Side,
    decode_polyline,
    destination_point,
    encode_polyline,
    ferry_intervals_km,
    haversine_km,
    initial_bearing_deg,
    km_at_index,
    measure_line,
    offset_point,
    point_at_km,
    segment_distance_km,
    simplify_indexes,
)
from planning.domain.values import Coordinate, PointRange

ORIGIN = Coordinate(latitude=0.0, longitude=0.0)
GOOGLE_EXAMPLE_POINTS = (
    Coordinate(latitude=38.5, longitude=-120.2),
    Coordinate(latitude=40.7, longitude=-120.95),
    Coordinate(latitude=43.252, longitude=-126.453),
)
GOOGLE_EXAMPLE_ENCODED = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"


def _equator_line(count: int, step_deg: float = 0.01) -> tuple[Coordinate, ...]:
    return tuple(Coordinate(latitude=0.0, longitude=index * step_deg) for index in range(count))


def test_haversine_one_degree_on_a_meridian() -> None:
    north = Coordinate(latitude=1.0, longitude=0.0)
    assert haversine_km(ORIGIN, north) == pytest.approx(KM_PER_DEGREE)
    assert haversine_km(north, ORIGIN) == pytest.approx(KM_PER_DEGREE)
    assert haversine_km(ORIGIN, ORIGIN) == 0.0


def test_haversine_known_city_pair() -> None:
    dallas = Coordinate(latitude=32.7767, longitude=-96.7970)
    oklahoma_city = Coordinate(latitude=35.4676, longitude=-97.5164)
    assert haversine_km(dallas, oklahoma_city) == pytest.approx(305.0, abs=2.0)


def test_measure_line_accumulates_segments() -> None:
    line = measure_line(_equator_line(3, step_deg=1.0))
    assert line.cumulative_km == pytest.approx((0.0, KM_PER_DEGREE, 2 * KM_PER_DEGREE))
    assert line.length_km == pytest.approx(2 * KM_PER_DEGREE)


def test_single_point_line_has_no_length() -> None:
    line = measure_line((ORIGIN,))
    assert line.length_km == 0.0
    assert point_at_km(line, 5.0) == ORIGIN


@pytest.mark.parametrize(
    ("index", "expected_degrees"),
    [(-3, 0.0), (0, 0.0), (1, 1.0), (2, 2.0), (99, 2.0)],
)
def test_km_at_index_clamps(index: int, expected_degrees: float) -> None:
    line = measure_line(_equator_line(3, step_deg=1.0))
    assert km_at_index(line, index) == pytest.approx(expected_degrees * KM_PER_DEGREE)


@pytest.mark.parametrize(
    ("distance_degrees", "expected_longitude"),
    [(-1.0, 0.0), (0.0, 0.0), (0.25, 0.25), (1.0, 1.0), (1.5, 1.5), (2.0, 2.0), (3.0, 2.0)],
)
def test_point_at_km_interpolates_and_clamps(
    distance_degrees: float, expected_longitude: float
) -> None:
    line = measure_line(_equator_line(3, step_deg=1.0))
    point = point_at_km(line, distance_degrees * KM_PER_DEGREE)
    assert point.latitude == pytest.approx(0.0)
    assert point.longitude == pytest.approx(expected_longitude)


def test_point_at_km_on_a_line_with_repeated_points() -> None:
    repeated = Coordinate(latitude=0.0, longitude=1.0)
    line = measure_line((ORIGIN, repeated, repeated, Coordinate(latitude=0.0, longitude=2.0)))
    assert point_at_km(line, KM_PER_DEGREE).longitude == pytest.approx(1.0)
    assert point_at_km(line, 1.5 * KM_PER_DEGREE).longitude == pytest.approx(1.5)


def test_segment_distance_perpendicular_and_beyond_the_end() -> None:
    start = ORIGIN
    end = Coordinate(latitude=0.0, longitude=1.0)
    above = Coordinate(latitude=0.1, longitude=0.5)
    beyond = Coordinate(latitude=0.0, longitude=1.1)
    assert segment_distance_km(above, start, end) == pytest.approx(0.1 * KM_PER_DEGREE)
    assert segment_distance_km(beyond, start, end) == pytest.approx(0.1 * KM_PER_DEGREE)
    assert segment_distance_km(beyond, end, end) == pytest.approx(0.1 * KM_PER_DEGREE)


def test_simplify_short_lines_keep_every_point() -> None:
    assert simplify_indexes(()) == ()
    assert simplify_indexes((ORIGIN,)) == (0,)
    assert simplify_indexes(_equator_line(2)) == (0, 1)


def test_simplify_straight_line_keeps_only_the_endpoints() -> None:
    assert simplify_indexes(_equator_line(50)) == (0, 49)


@pytest.mark.parametrize(
    ("bump_m", "expected"),
    [(29.0, (0, 20)), (31.0, (0, 10, 20))],
)
def test_simplify_keeps_a_bump_only_beyond_the_tolerance(
    bump_m: float, expected: tuple[int, ...]
) -> None:
    points = list(_equator_line(21))
    points[10] = Coordinate(latitude=bump_m / 1000 / KM_PER_DEGREE, longitude=0.1)
    assert simplify_indexes(points, tolerance_m=30.0) == expected


def test_simplify_every_removed_point_stays_within_the_tolerance() -> None:
    points = tuple(
        Coordinate(latitude=0.02 * math.sin(index / 7), longitude=index * 0.001)
        for index in range(2000)
    )
    kept = simplify_indexes(points, tolerance_m=30.0)
    assert kept[0] == 0
    assert kept[-1] == len(points) - 1
    assert len(kept) < len(points)
    for start_index, end_index in itertools.pairwise(kept):
        for index in range(start_index + 1, end_index):
            distance_km = segment_distance_km(points[index], points[start_index], points[end_index])
            assert distance_km <= 0.030 + 1e-6


def test_simplify_handles_twenty_thousand_points() -> None:
    points = tuple(
        Coordinate(latitude=0.001 * (index % 3), longitude=index * 0.0009) for index in range(20000)
    )
    kept = simplify_indexes(points, tolerance_m=30.0)
    assert kept[0] == 0
    assert kept[-1] == 19999


def test_polyline_matches_the_reference_example() -> None:
    assert encode_polyline(GOOGLE_EXAMPLE_POINTS) == GOOGLE_EXAMPLE_ENCODED
    assert decode_polyline(GOOGLE_EXAMPLE_ENCODED) == GOOGLE_EXAMPLE_POINTS


def test_polyline_round_trip_at_precision_five() -> None:
    points = (
        Coordinate(latitude=-33.865143, longitude=151.2099),
        Coordinate(latitude=-89.99999, longitude=179.99999),
        Coordinate(latitude=0.0, longitude=-0.00001),
    )
    decoded = decode_polyline(encode_polyline(points))
    for original, restored in zip(points, decoded, strict=True):
        assert restored.latitude == pytest.approx(original.latitude, abs=1e-5)
        assert restored.longitude == pytest.approx(original.longitude, abs=1e-5)


def test_polyline_empty() -> None:
    assert encode_polyline(()) == ""
    assert decode_polyline("") == ()


@pytest.mark.parametrize(
    "encoded",
    [
        "_p~iF~ps|U_ulLnnqC_mqN",
        "_p~iF",
        "_p~iF~ps|U_",
        "_p~iF ps|U",
        "~~~~~~~~~~?",
        encode_polyline((Coordinate(latitude=91.0, longitude=0.0),)),
        encode_polyline((Coordinate(latitude=0.0, longitude=181.0),)),
    ],
)
def test_polyline_rejects_malformed_text(encoded: str) -> None:
    with pytest.raises(PolylineInvalid):
        decode_polyline(encoded)


@pytest.mark.parametrize(
    ("end", "expected_deg"),
    [
        (Coordinate(latitude=1.0, longitude=0.0), 0.0),
        (Coordinate(latitude=0.0, longitude=1.0), 90.0),
        (Coordinate(latitude=-1.0, longitude=0.0), 180.0),
        (Coordinate(latitude=0.0, longitude=-1.0), 270.0),
    ],
)
def test_initial_bearing(end: Coordinate, expected_deg: float) -> None:
    assert initial_bearing_deg(ORIGIN, end) == pytest.approx(expected_deg)


def test_destination_point_round_trips_distance_and_bearing() -> None:
    start = Coordinate(latitude=40.0, longitude=-100.0)
    end = destination_point(start, 45.0, 100.0)
    assert haversine_km(start, end) == pytest.approx(100.0)
    assert initial_bearing_deg(start, end) == pytest.approx(45.0)


def test_destination_point_wraps_longitude() -> None:
    start = Coordinate(latitude=0.0, longitude=179.9)
    end = destination_point(start, 90.0, 0.2 * KM_PER_DEGREE)
    assert end.longitude == pytest.approx(-179.9)


@pytest.mark.parametrize(("side", "sign"), [(Side.LEFT, 1.0), (Side.RIGHT, -1.0)])
def test_offset_point_is_perpendicular_on_the_named_side(side: Side, sign: float) -> None:
    line = measure_line(_equator_line(101))
    middle_km = line.length_km / 2
    offset = offset_point(line, middle_km, 20.0, side)
    assert math.copysign(1.0, offset.latitude) == sign
    assert offset.longitude == pytest.approx(0.5, abs=1e-6)
    assert haversine_km(point_at_km(line, middle_km), offset) == pytest.approx(20.0)


def test_offset_point_on_a_line_without_length() -> None:
    line = measure_line((ORIGIN, ORIGIN))
    with pytest.raises(DegenerateLine):
        offset_point(line, 0.0, 10.0, Side.LEFT)


def test_ferry_intervals_follow_point_indexes() -> None:
    line = measure_line(_equator_line(5, step_deg=1.0))
    intervals = ferry_intervals_km(
        line, (PointRange(start_index=1, end_index=2), PointRange(start_index=4, end_index=3))
    )
    assert intervals == (
        KmInterval(start_km=line.cumulative_km[1], end_km=line.cumulative_km[2]),
        KmInterval(start_km=line.cumulative_km[3], end_km=line.cumulative_km[4]),
    )
    assert intervals[0].contains(1.5 * KM_PER_DEGREE)
    assert not intervals[0].contains(2.5 * KM_PER_DEGREE)
