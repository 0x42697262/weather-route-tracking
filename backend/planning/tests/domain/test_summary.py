import pytest

from planning.domain.stretches import RouteSample, Stretch, StretchKind, build_stretches
from planning.domain.summary import RouteWarning, summarize
from rulesets.domain.schema import StretchMethod
from shared.risk_levels import RISK_LEVELS, RiskLevel

LOW = RiskLevel.LOW
MODERATE = RiskLevel.MODERATE
HIGH = RiskLevel.HIGH
SEVERE = RiskLevel.SEVERE
NO_TRAVEL = RiskLevel.NO_TRAVEL
RATED = StretchKind.RATED
UNKNOWN = StretchKind.UNKNOWN
FERRY = StretchKind.FERRY


def test_distances_per_level_with_every_level_present() -> None:
    summary = summarize((Stretch(0, 10, LOW, RATED), Stretch(10, 40, HIGH, RATED)))

    assert dict(summary.distance_km_by_level) == {
        LOW: 10,
        MODERATE: 0,
        HIGH: 30,
        SEVERE: 0,
        NO_TRAVEL: 0,
    }
    assert set(summary.distance_km_by_level) == set(RISK_LEVELS)
    assert (summary.unknown_km, summary.ferry_km, summary.total_km) == (0, 0, 40)
    assert summary.known_km == 40
    assert summary.warnings == ()
    assert summary.blocked is False


def test_average_risk_is_score_weighted_by_km() -> None:
    summary = summarize(
        (
            Stretch(0, 10, LOW, RATED),
            Stretch(10, 40, HIGH, RATED),
            Stretch(40, 50, None, UNKNOWN),
            Stretch(50, 60, None, FERRY),
        )
    )

    expected = (RISK_LEVELS[LOW].score * 10 + RISK_LEVELS[HIGH].score * 30) / 40
    assert summary.average_risk == pytest.approx(expected)


def test_unknown_distance_and_warning() -> None:
    summary = summarize((Stretch(0, 10, MODERATE, RATED), Stretch(10, 25, None, UNKNOWN)))

    assert summary.unknown_km == 15
    assert summary.known_km == 10
    assert summary.warnings == (RouteWarning.UNKNOWN_WEATHER,)


def test_not_rated_ferry_is_ferry_distance_out_of_average_and_warned() -> None:
    summary = summarize((Stretch(0, 10, SEVERE, RATED), Stretch(10, 30, None, FERRY)))

    assert summary.ferry_km == 20
    assert summary.unknown_km == 0
    assert summary.distance_km_by_level[SEVERE] == 10
    assert summary.average_risk == RISK_LEVELS[SEVERE].score
    assert summary.warnings == (RouteWarning.FERRY_CROSSING,)


def test_rated_ferry_counts_at_its_level() -> None:
    summary = summarize((Stretch(0, 10, LOW, RATED), Stretch(10, 30, MODERATE, FERRY)))

    assert summary.ferry_km == 0
    assert summary.distance_km_by_level[MODERATE] == 20
    assert summary.average_risk == pytest.approx(RISK_LEVELS[MODERATE].score * 20 / 30)
    assert summary.warnings == (RouteWarning.FERRY_CROSSING,)


def test_no_known_distance_has_no_average() -> None:
    summary = summarize((Stretch(0, 10, None, UNKNOWN),))

    assert summary.average_risk is None
    assert summary.known_km == 0


def test_no_stretches() -> None:
    summary = summarize(())

    assert summary.total_km == 0
    assert summary.average_risk is None
    assert summary.warnings == ()


def test_blocking_level_sets_flag_and_warning() -> None:
    blocking = [level for level, info in RISK_LEVELS.items() if info.blocks_recommendation]
    stretches = tuple(
        Stretch(index * 10, index * 10 + 10, level, RATED) for index, level in enumerate(blocking)
    )

    summary = summarize((*stretches, Stretch(100, 110, None, UNKNOWN)))

    assert summary.blocked is True
    assert summary.warnings == (RouteWarning.UNKNOWN_WEATHER, RouteWarning.HAS_BLOCKING_LEVEL)


def test_rounding_noise_at_a_blocking_level_does_not_block() -> None:
    blocking = next(level for level, info in RISK_LEVELS.items() if info.blocks_recommendation)

    summary = summarize((Stretch(0, 10, LOW, RATED), Stretch(10, 10.000001, blocking, RATED)))

    assert summary.blocked is False
    assert RouteWarning.HAS_BLOCKING_LEVEL not in summary.warnings


def test_distances_add_up_to_route_length() -> None:
    levels: list[RiskLevel | None] = [LOW, HIGH, None, SEVERE, MODERATE, NO_TRAVEL, LOW, None, LOW]
    samples = tuple(RouteSample(index * 17.3, level, None) for index, level in enumerate(levels))
    route_km = samples[-1].distance_km

    summary = summarize(
        build_stretches(samples, StretchMethod.WORSE_END, ((20, 41.5), (100, 110)), None)
    )

    parts_km = sum(summary.distance_km_by_level.values()) + summary.unknown_km + summary.ferry_km
    assert parts_km == pytest.approx(route_km)
    assert summary.total_km == pytest.approx(route_km)
    assert summary.ferry_km == pytest.approx(31.5)


def test_worst_level_blocking_and_weather_rated_distance() -> None:
    summary = summarize(
        (
            Stretch(0, 10, LOW, RATED),
            Stretch(10, 15, NO_TRAVEL, RATED),
            Stretch(15, 20, None, UNKNOWN),
            Stretch(20, 30, MODERATE, FERRY),
        )
    )

    assert summary.worst_level is NO_TRAVEL
    assert summary.blocking_km == 5
    assert summary.weather_rated_km == 15


def test_worst_level_ignores_rounding_noise_and_is_none_without_levels() -> None:
    noisy = summarize((Stretch(0, 10, LOW, RATED), Stretch(10, 10.001, SEVERE, RATED)))
    unknown = summarize((Stretch(0, 10, None, UNKNOWN),))

    assert noisy.worst_level is LOW
    assert unknown.worst_level is None
