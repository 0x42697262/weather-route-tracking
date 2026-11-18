import itertools
import math

import pytest

from planning.domain.corridor import (
    CorridorCapUnreachable,
    build_corridor,
    cell_reach_km,
)
from planning.domain.geometry import segment_distance_km
from planning.domain.values import Coordinate
from planning.domain.weather_lookup import cell_key

BUFFER_KM = 25.0
CELL_DEG = 0.1


def _wiggly_line(start_lat: float = 0.0, length_deg: float = 2.0) -> list[Coordinate]:
    count = round(length_deg / 0.005) + 1
    return [
        Coordinate(latitude=start_lat + 0.08 * math.sin(index / 25), longitude=index * 0.005)
        for index in range(count)
    ]


def _distance_to_line_km(point: Coordinate, line: list[Coordinate]) -> float:
    if len(line) == 1:
        return segment_distance_km(point, line[0], line[0])
    return min(segment_distance_km(point, start, end) for start, end in itertools.pairwise(line))


def _expected_cells(
    lines: list[list[Coordinate]], cell_deg: float, rows: range, cols: range
) -> set[tuple[float, float]]:
    expected = set()
    for row, col in itertools.product(rows, cols):
        center = Coordinate(latitude=row * cell_deg, longitude=col * cell_deg)
        reach_km = cell_reach_km(center.latitude, cell_deg, BUFFER_KM)
        if min(_distance_to_line_km(center, line) for line in lines) <= reach_km:
            expected.add((round(center.latitude, 6), round(center.longitude, 6)))
    return expected


def _as_pairs(cells: tuple[Coordinate, ...]) -> set[tuple[float, float]]:
    return {(cell.latitude, cell.longitude) for cell in cells}


def test_cells_inside_the_buffer_and_none_outside() -> None:
    line = _wiggly_line()
    corridor = build_corridor([line], CELL_DEG, 10000, buffer_km=BUFFER_KM)
    assert corridor.cell_size_deg == CELL_DEG
    expected = _expected_cells([line], CELL_DEG, range(-8, 9), range(-8, 29))
    assert _as_pairs(corridor.cells) == expected
    assert list(corridor.cells) == sorted(
        corridor.cells, key=lambda cell: (cell.latitude, cell.longitude)
    )


def test_every_point_of_the_line_is_covered() -> None:
    line = _wiggly_line()
    corridor = build_corridor([line], CELL_DEG, 10000, buffer_km=BUFFER_KM)
    cells = _as_pairs(corridor.cells)
    for point in line:
        center = (
            round(round(point.latitude / CELL_DEG) * CELL_DEG, 6),
            round(round(point.longitude / CELL_DEG) * CELL_DEG, 6),
        )
        assert center in cells


def test_two_lines_share_cells() -> None:
    first = _wiggly_line()
    second = _wiggly_line(start_lat=0.5)
    corridor = build_corridor([first, second], CELL_DEG, 10000, buffer_km=BUFFER_KM)
    expected = _expected_cells([first, second], CELL_DEG, range(-8, 14), range(-8, 29))
    assert _as_pairs(corridor.cells) == expected
    assert len(corridor.cells) == len(set(corridor.cells))


def test_single_point_line() -> None:
    point = [Coordinate(latitude=0.0, longitude=0.0)]
    corridor = build_corridor([point], CELL_DEG, 10000, buffer_km=BUFFER_KM)
    assert _as_pairs(corridor.cells) == _expected_cells(
        [point], CELL_DEG, range(-6, 7), range(-6, 7)
    )


def test_cell_size_grows_to_respect_the_cap() -> None:
    line = _wiggly_line(length_deg=6.0)
    unbounded = build_corridor([line], CELL_DEG, 10000, buffer_km=BUFFER_KM)
    cap = len(unbounded.cells) // 3
    corridor = build_corridor([line], CELL_DEG, cap, buffer_km=BUFFER_KM)
    assert corridor.cell_size_deg > CELL_DEG
    assert len(corridor.cells) <= cap
    smaller = build_corridor([line], corridor.cell_size_deg / 2, 10000, buffer_km=BUFFER_KM)
    assert len(smaller.cells) > cap


def test_unreachable_cap_is_an_error() -> None:
    with pytest.raises(CorridorCapUnreachable):
        build_corridor([_wiggly_line()], CELL_DEG, 0, buffer_km=BUFFER_KM)


def test_no_lines_give_no_cells() -> None:
    assert build_corridor([], CELL_DEG, 10).cells == ()


def test_long_lines_stay_fast() -> None:
    lines = [
        [
            Coordinate(
                latitude=30.0 + offset + 0.05 * math.sin(index / 300), longitude=index * 0.0007
            )
            for index in range(20000)
        ]
        for offset in (0.0, 0.1, 0.2, 0.3, 0.4)
    ]
    corridor = build_corridor(lines, CELL_DEG, 300)
    assert 0 < len(corridor.cells) <= 300


def test_cell_centers_are_weather_cell_keys() -> None:
    line = _wiggly_line(start_lat=-1.0, length_deg=6.0)
    for cell_deg in (CELL_DEG, 0.25):
        corridor = build_corridor([line], cell_deg, 10000, buffer_km=BUFFER_KM)
        for cell in corridor.cells:
            assert cell_key(cell, corridor.cell_size_deg) == cell
