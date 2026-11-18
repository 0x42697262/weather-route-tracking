import math

import pytest

from planning.constants import KM_PER_DEGREE, ROUTE_MAX_OVERLAP_SHARE, ROUTE_MAX_TIME_RATIO
from planning.domain.geometry import measure_line
from planning.domain.route_distinct import (
    KeptRoutes,
    RejectReason,
    is_distinct,
    overlap_share,
    time_ratio,
)
from planning.domain.values import Coordinate

FASTEST_S = 10000.0
STEP_DEG = 0.01


def _equator(start_deg: float, end_deg: float, latitude: float = 0.0) -> list[Coordinate]:
    count = round((end_deg - start_deg) / STEP_DEG)
    return [
        Coordinate(latitude=latitude, longitude=start_deg + index * STEP_DEG)
        for index in range(count + 1)
    ]


def _kept(*lines: list[Coordinate]) -> KeptRoutes:
    kept = KeptRoutes()
    for line in lines:
        kept.add(line)
    return kept


def _diverging_candidate(target_share: float) -> list[Coordinate]:
    shifted_deg = 0.1
    total_km = 10 * KM_PER_DEGREE + shifted_deg * KM_PER_DEGREE
    split_deg = round(target_share * total_km / KM_PER_DEGREE, 2)
    return _equator(0.0, split_deg) + _equator(split_deg, 10.0, latitude=shifted_deg)


def test_identical_lines_fully_overlap() -> None:
    line = _equator(0.0, 10.0)
    decision = is_distinct(line, FASTEST_S, _kept(line), FASTEST_S)
    assert decision.overlap_share == pytest.approx(1.0)
    assert not decision.keep
    assert decision.reason is RejectReason.OVERLAPS_KEPT_ROUTE


def test_fully_separate_lines_do_not_overlap() -> None:
    decision = is_distinct(
        _equator(0.0, 10.0, latitude=1.0), FASTEST_S, _kept(_equator(0.0, 10.0)), FASTEST_S
    )
    assert decision.overlap_share == 0.0
    assert decision.keep
    assert decision.reason is None
    assert decision.time_ratio == pytest.approx(1.0)


def test_nothing_kept_means_no_overlap() -> None:
    assert overlap_share(_equator(0.0, 1.0), KeptRoutes()) == 0.0


def test_overlap_share_measures_the_shared_length() -> None:
    candidate = _equator(0.0, 5.0) + _equator(5.0, 10.0, latitude=0.1)
    expected = measure_line(_equator(0.0, 5.0)).length_km / measure_line(candidate).length_km
    assert overlap_share(candidate, _kept(_equator(0.0, 10.0))) == pytest.approx(
        expected, abs=0.002
    )


@pytest.mark.parametrize(
    ("share", "expected_reason"),
    [
        (ROUTE_MAX_OVERLAP_SHARE - 0.01, None),
        (ROUTE_MAX_OVERLAP_SHARE + 0.01, RejectReason.OVERLAPS_KEPT_ROUTE),
    ],
)
def test_overlap_just_under_and_over_the_limit(
    share: float, expected_reason: RejectReason | None
) -> None:
    candidate = _diverging_candidate(share)
    decision = is_distinct(candidate, FASTEST_S, _kept(_equator(0.0, 10.0)), FASTEST_S)
    assert decision.reason is expected_reason
    assert decision.keep is (expected_reason is None)
    assert decision.overlap_share == pytest.approx(share, abs=0.005)


@pytest.mark.parametrize(
    ("ratio", "expected_reason"),
    [
        (1.0, None),
        (ROUTE_MAX_TIME_RATIO, None),
        (ROUTE_MAX_TIME_RATIO + 1e-6, RejectReason.TOO_SLOW),
    ],
)
def test_time_just_inside_and_outside_the_limit(
    ratio: float, expected_reason: RejectReason | None
) -> None:
    decision = is_distinct(
        _equator(0.0, 1.0, latitude=1.0), FASTEST_S * ratio, _kept(_equator(0.0, 1.0)), FASTEST_S
    )
    assert decision.reason is expected_reason
    assert decision.keep is (expected_reason is None)


def test_overlap_is_reported_before_slowness() -> None:
    line = _equator(0.0, 1.0)
    decision = is_distinct(line, FASTEST_S * 3, _kept(line), FASTEST_S)
    assert decision.reason is RejectReason.OVERLAPS_KEPT_ROUTE
    assert decision.time_ratio == pytest.approx(3.0)


def test_overlap_counts_every_kept_line() -> None:
    candidate = _equator(0.0, 10.0)
    kept = _kept(_equator(0.0, 5.0), _equator(5.0, 10.0))
    assert len(kept) == 2
    assert overlap_share(candidate, kept) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("candidate_s", "fastest_s", "expected"),
    [(10.0, 0.0, math.inf), (0.0, 0.0, 1.0), (15.0, 10.0, 1.5)],
)
def test_time_ratio(candidate_s: float, fastest_s: float, expected: float) -> None:
    assert time_ratio(candidate_s, fastest_s) == expected


def test_long_lines_stay_fast() -> None:
    def wiggle(offset_deg: float) -> list[Coordinate]:
        return [
            Coordinate(latitude=offset_deg + 0.05 * math.sin(index / 300), longitude=index * 0.0007)
            for index in range(20000)
        ]

    kept = _kept(wiggle(0.0), wiggle(0.3), wiggle(0.6))
    assert overlap_share(wiggle(0.0), kept) == pytest.approx(1.0)
    assert overlap_share(wiggle(1.0), kept) == 0.0
