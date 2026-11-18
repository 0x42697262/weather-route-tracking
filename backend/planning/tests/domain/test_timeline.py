from dataclasses import replace

import pytest

from planning.constants import SECONDS_PER_HOUR
from planning.domain.geometry import RouteLine, measure_line
from planning.domain.timeline import LegKind, StopKind, Timeline, build_timeline
from planning.domain.values import Coordinate, PointRange, ProgressPoint, ProviderRoute
from rulesets.domain.defaults import default_rule_set_document
from rulesets.domain.schema import RuleSet
from rulesets.domain.validator import validate_rule_set

HOUR_S = SECONDS_PER_HOUR
POINT_STEP_DEG = 0.1


def _rules(
    factor: float = 1.0, cap_kmh: float | None = None, break_s: float | None = None
) -> RuleSet:
    rules = validate_rule_set(default_rule_set_document())
    rest = rules.rest_rules if break_s is None else replace(rules.rest_rules, break_s=break_s)
    return replace(rules, truck_speed_factor=factor, truck_max_speed_kmh=cap_kmh, rest_rules=rest)


def _line(point_count: int) -> RouteLine:
    return measure_line(
        tuple(
            Coordinate(latitude=0.0, longitude=index * POINT_STEP_DEG)
            for index in range(point_count)
        )
    )


def _route(
    line: RouteLine,
    marks: list[tuple[int, float]],
    ferries: tuple[PointRange, ...] = (),
) -> ProviderRoute:
    progress = tuple(
        ProgressPoint(point_index=index, distance_km=line.cumulative_km[index], elapsed_s=elapsed_s)
        for index, elapsed_s in marks
    )
    return ProviderRoute(
        points=line.points,
        distance_km=line.length_km,
        travel_time_s=marks[-1][1] if marks else 0.0,
        progress=progress,
        ferry_sections=ferries,
    )


def _plan(hours: float, rules: RuleSet, *, include_rest: bool = True) -> tuple[RouteLine, Timeline]:
    line = _line(201)
    route = _route(line, [(0, 0.0), (200, hours * HOUR_S)])
    return line, build_timeline(route, line, rules, include_rest=include_rest)


def _segment_hours_at(line: RouteLine, speeds_kmh: list[float]) -> list[tuple[int, float]]:
    marks = [(0, 0.0)]
    for number, speed_kmh in enumerate(speeds_kmh, start=1):
        index = number * 10
        segment_km = line.cumulative_km[index] - line.cumulative_km[index - 10]
        marks.append((index, marks[-1][1] + segment_km / speed_kmh * HOUR_S))
    return marks


def test_factor_one_keeps_provider_times() -> None:
    line = _line(31)
    route = _route(line, _segment_hours_at(line, [120.0, 60.0, 90.0]))
    timeline = build_timeline(route, line, _rules(), include_rest=False)
    assert timeline.elapsed_s == pytest.approx(route.travel_time_s)
    assert timeline.driving_s == pytest.approx(route.travel_time_s)
    for leg, (_, mark_s) in zip(timeline.legs, route_marks(route)[1:], strict=True):
        assert leg.end_elapsed_s == pytest.approx(mark_s)


def route_marks(route: ProviderRoute) -> list[tuple[int, float]]:
    return [(entry.point_index, entry.elapsed_s) for entry in route.progress]


def test_factor_below_one_slows_every_segment() -> None:
    line = _line(31)
    route = _route(line, _segment_hours_at(line, [120.0, 60.0, 90.0]))
    timeline = build_timeline(route, line, _rules(factor=0.8), include_rest=False)
    assert timeline.elapsed_s == pytest.approx(route.travel_time_s / 0.8)


def test_cap_applies_only_to_segments_above_it() -> None:
    line = _line(21)
    route = _route(line, _segment_hours_at(line, [120.0, 60.0]))
    timeline = build_timeline(route, line, _rules(cap_kmh=100.0), include_rest=False)
    fast_km = line.cumulative_km[10]
    slow_km = line.cumulative_km[20] - line.cumulative_km[10]
    expected_s = fast_km / 100.0 * HOUR_S + slow_km / 60.0 * HOUR_S
    assert timeline.elapsed_s == pytest.approx(expected_s)


def test_no_cap_keeps_fast_segments() -> None:
    line = _line(21)
    route = _route(line, _segment_hours_at(line, [120.0, 60.0]))
    timeline = build_timeline(route, line, _rules(cap_kmh=None), include_rest=False)
    assert timeline.elapsed_s == pytest.approx(route.travel_time_s)


def test_provider_with_totals_only_is_one_segment_at_average_speed() -> None:
    line = _line(21)
    route = ProviderRoute(
        points=line.points,
        distance_km=line.length_km,
        travel_time_s=line.length_km / 120.0 * HOUR_S,
        progress=(),
        ferry_sections=(),
    )
    timeline = build_timeline(route, line, _rules(cap_kmh=100.0), include_rest=False)
    assert len(timeline.legs) == 1
    assert timeline.elapsed_s == pytest.approx(line.length_km / 100.0 * HOUR_S)
    assert timeline.elapsed_at(line.length_km / 2) == pytest.approx(timeline.elapsed_s / 2)


def test_zero_time_segment_takes_the_cap_or_nothing() -> None:
    line = _line(11)
    route = _route(line, [(0, 0.0), (10, 0.0)])
    capped = build_timeline(route, line, _rules(cap_kmh=100.0), include_rest=False)
    uncapped = build_timeline(route, line, _rules(cap_kmh=None), include_rest=False)
    assert capped.elapsed_s == pytest.approx(line.length_km / 100.0 * HOUR_S)
    assert uncapped.elapsed_s == 0.0


def test_zero_length_segment_keeps_its_time() -> None:
    line = _line(11)
    route = _route(line, [(0, 0.0), (5, HOUR_S), (5, 2 * HOUR_S), (10, 3 * HOUR_S)])
    timeline = build_timeline(route, line, _rules(), include_rest=False)
    middle_km = line.cumulative_km[5]
    assert timeline.elapsed_s == pytest.approx(3 * HOUR_S)
    assert timeline.elapsed_at(middle_km) == pytest.approx(HOUR_S)
    assert timeline.position_at(1.5 * HOUR_S) == pytest.approx(middle_km)


@pytest.mark.parametrize("hours", [7.5, 8.0])
def test_under_eight_hours_on_and_off_are_identical(hours: float) -> None:
    _, with_rest = _plan(hours, _rules())
    _, without_rest = _plan(hours, _rules(), include_rest=False)
    assert with_rest == without_rest
    assert with_rest.stops == ()


def test_break_exactly_at_eight_hours_of_driving() -> None:
    line, timeline = _plan(9.0, _rules())
    (stop,) = timeline.stops
    assert stop.kind is StopKind.BREAK
    assert stop.start_elapsed_s == pytest.approx(8 * HOUR_S)
    assert stop.duration_s == pytest.approx(0.5 * HOUR_S)
    assert stop.distance_km == pytest.approx(line.length_km * 8 / 9)
    assert timeline.elapsed_s == pytest.approx(9.5 * HOUR_S)
    assert timeline.driving_s == pytest.approx(9 * HOUR_S)
    assert timeline.rest_s == pytest.approx(0.5 * HOUR_S)


def test_segment_is_split_at_the_limit() -> None:
    line, timeline = _plan(9.0, _rules())
    first, second = timeline.legs
    assert first.end_km == pytest.approx(timeline.stops[0].distance_km)
    assert second.start_km == pytest.approx(first.end_km)
    assert first.end_elapsed_s == pytest.approx(8 * HOUR_S)
    assert second.start_elapsed_s == pytest.approx(8.5 * HOUR_S)
    assert second.end_km == pytest.approx(line.length_km)


def test_off_duty_at_eleven_hours_of_driving() -> None:
    line, timeline = _plan(12.0, _rules())
    assert [stop.kind for stop in timeline.stops] == [StopKind.BREAK, StopKind.OFF_DUTY]
    off_duty = timeline.stops[1]
    assert off_duty.start_elapsed_s == pytest.approx(11.5 * HOUR_S)
    assert off_duty.duration_s == pytest.approx(10 * HOUR_S)
    assert off_duty.distance_km == pytest.approx(line.length_km * 11 / 12)
    assert timeline.elapsed_s == pytest.approx(22.5 * HOUR_S)


def test_off_duty_at_fourteen_hours_of_shift() -> None:
    line, timeline = _plan(12.0, _rules(break_s=4 * HOUR_S))
    assert [stop.kind for stop in timeline.stops] == [StopKind.BREAK, StopKind.OFF_DUTY]
    off_duty = timeline.stops[1]
    assert off_duty.start_elapsed_s == pytest.approx(14 * HOUR_S)
    assert off_duty.distance_km == pytest.approx(line.length_km * 10 / 12)
    assert timeline.elapsed_s == pytest.approx((12 + 4 + 10) * HOUR_S)


def test_off_duty_starts_a_new_shift() -> None:
    _, timeline = _plan(31.0, _rules())
    assert [stop.kind for stop in timeline.stops] == [
        StopKind.BREAK,
        StopKind.OFF_DUTY,
        StopKind.BREAK,
        StopKind.OFF_DUTY,
        StopKind.BREAK,
    ]
    assert [stop.start_elapsed_s / HOUR_S for stop in timeline.stops] == pytest.approx(
        [8.0, 11.5, 29.5, 33.0, 51.0]
    )


def test_rest_switched_off_inserts_nothing() -> None:
    _, timeline = _plan(25.0, _rules(), include_rest=False)
    assert timeline.stops == ()
    assert timeline.rest_s == 0.0
    assert timeline.elapsed_s == pytest.approx(25 * HOUR_S)


def test_elapsed_at_a_stop_is_the_arrival_and_the_marker_holds_still() -> None:
    line, timeline = _plan(9.0, _rules())
    stop_km = timeline.stops[0].distance_km
    assert timeline.elapsed_at(stop_km) == pytest.approx(8 * HOUR_S)
    assert timeline.elapsed_at(line.length_km * 8.5 / 9) == pytest.approx(9 * HOUR_S)
    assert timeline.elapsed_at(-1.0) == 0.0
    assert timeline.elapsed_at(line.length_km + 1.0) == pytest.approx(9.5 * HOUR_S)
    assert timeline.position_at(8.25 * HOUR_S) == pytest.approx(stop_km)
    assert timeline.position_at(9.0 * HOUR_S) == pytest.approx(line.length_km * 8.5 / 9)
    assert timeline.position_at(-5.0) == 0.0
    assert timeline.position_at(99 * HOUR_S) == pytest.approx(line.length_km)


def _ferry_route() -> tuple[RouteLine, ProviderRoute]:
    line = _line(31)
    route = _route(
        line,
        [(0, 0.0), (10, 7 * HOUR_S), (20, 9 * HOUR_S), (30, 11 * HOUR_S)],
        ferries=(PointRange(start_index=10, end_index=20),),
    )
    return line, route


def test_ferry_time_is_unchanged_and_not_driving() -> None:
    line, route = _ferry_route()
    timeline = build_timeline(route, line, _rules(factor=0.5), include_rest=False)
    assert [leg.kind for leg in timeline.legs] == [
        LegKind.DRIVING,
        LegKind.FERRY,
        LegKind.DRIVING,
    ]
    assert timeline.ferry_s == pytest.approx(2 * HOUR_S)
    assert timeline.driving_s == pytest.approx(18 * HOUR_S)
    assert timeline.elapsed_s == pytest.approx(20 * HOUR_S)


def test_ferry_does_not_count_toward_the_break() -> None:
    line, route = _ferry_route()
    timeline = build_timeline(route, line, _rules(), include_rest=True)
    (stop,) = timeline.stops
    assert stop.kind is StopKind.BREAK
    assert stop.start_elapsed_s == pytest.approx(10 * HOUR_S)
    expected_km = (line.cumulative_km[20] + line.cumulative_km[30]) / 2
    assert stop.distance_km == pytest.approx(expected_km)
    assert timeline.elapsed_s == pytest.approx(11.5 * HOUR_S)


def test_ferry_section_inside_a_progress_segment_is_split_by_distance() -> None:
    line = _line(31)
    route = _route(
        line, [(0, 0.0), (30, 3 * HOUR_S)], ferries=(PointRange(start_index=10, end_index=20),)
    )
    timeline = build_timeline(route, line, _rules(factor=0.5), include_rest=False)
    assert [leg.kind for leg in timeline.legs] == [
        LegKind.DRIVING,
        LegKind.FERRY,
        LegKind.DRIVING,
    ]
    assert timeline.ferry_s == pytest.approx(HOUR_S)
    assert timeline.driving_s == pytest.approx(4 * HOUR_S)
