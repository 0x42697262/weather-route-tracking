from dataclasses import replace
from types import MappingProxyType

import pytest

from planning.domain.ranking import (
    RANKING_KEY_NAMES,
    NoRecommendationReason,
    NotRecommendableReason,
    RankingInput,
    rank,
)
from planning.domain.summary import RouteSummary
from shared.risk_levels import LEVELS_BY_SCORE, RISK_LEVELS, RiskLevel

LOW = RiskLevel.LOW
HIGH = RiskLevel.HIGH
SEVERE = RiskLevel.SEVERE
NO_TRAVEL = RiskLevel.NO_TRAVEL


KNOWN_WEATHER_KM = 100.0


def _route(
    route_id: str,
    distances: dict[RiskLevel, float] | None = None,
    average_risk: float | None = 0.5,
    travel_time_s: float = 3600,
    weather_rated_km: float | None = None,
) -> RankingInput:
    by_level = dict.fromkeys(LEVELS_BY_SCORE, 0.0) | (distances or {})
    blocked = any(
        RISK_LEVELS[level].blocks_recommendation and km > 0 for level, km in by_level.items()
    )
    summary = RouteSummary(
        distance_km_by_level=MappingProxyType(by_level),
        unknown_km=0,
        ferry_km=0,
        total_km=sum(by_level.values()),
        weather_rated_km=(
            weather_rated_km
            if weather_rated_km is not None
            else KNOWN_WEATHER_KM * (average_risk is not None)
        ),
        worst_level=None,
        blocking_km=0.0,
        average_risk=average_risk,
        blocked=blocked,
        warnings=(),
    )
    return RankingInput(route_id=route_id, summary=summary, travel_time_s=travel_time_s)


def test_key_names_follow_the_level_table() -> None:
    ranked = [level for level in reversed(LEVELS_BY_SCORE) if RISK_LEVELS[level].ranked]

    assert (
        *(f"{level}_km" for level in ranked),
        "average_risk",
        "travel_time_s",
    ) == RANKING_KEY_NAMES
    assert RANKING_KEY_NAMES == (
        "no_travel_km",
        "severe_km",
        "high_km",
        "average_risk",
        "travel_time_s",
    )


@pytest.mark.parametrize(
    ("worse", "better"),
    [
        (_route("a", {NO_TRAVEL: 1, LOW: 99}), _route("b", {SEVERE: 90, HIGH: 10})),
        (_route("a", {SEVERE: 2, HIGH: 0}), _route("b", {SEVERE: 1, HIGH: 50})),
        (_route("a", {HIGH: 2}, average_risk=0.1), _route("b", {HIGH: 1}, average_risk=3)),
        (
            _route("a", {HIGH: 1}, average_risk=0.6, travel_time_s=100),
            _route("b", {HIGH: 1}, average_risk=0.5, travel_time_s=9000),
        ),
        (
            _route("a", {HIGH: 1}, average_risk=0.5, travel_time_s=3601),
            _route("b", {HIGH: 1}, average_risk=0.5, travel_time_s=3600),
        ),
    ],
    ids=RANKING_KEY_NAMES,
)
def test_each_key_decides_when_earlier_keys_tie(worse: RankingInput, better: RankingInput) -> None:
    assert rank((worse, better)).order == ("b", "a")
    assert rank((better, worse)).order == ("b", "a")


def test_rounding_prevents_noise_from_deciding() -> None:
    first = _route("a", {SEVERE: 10.0000001}, average_risk=1.0000001, travel_time_s=3600.2)
    second = _route("b", {SEVERE: 10.0}, average_risk=1.0, travel_time_s=3600)

    ranking = rank((first, second))

    assert ranking.order == ("a", "b")
    assert ranking.keys[0].values == ranking.keys[1].values


def test_full_ties_keep_input_order() -> None:
    assert rank((_route("x"), _route("y"), _route("z"))).order == ("x", "y", "z")


def test_route_with_no_known_weather_sorts_last() -> None:
    unknown = _route("a", average_risk=None, travel_time_s=1)
    risky = _route("b", {NO_TRAVEL: 50}, average_risk=4, travel_time_s=9999)

    ranking = rank((unknown, risky))

    assert ranking.order == ("b", "a")
    assert ranking.keys[1].has_known_weather is False
    assert ranking.keys[1].values[RANKING_KEY_NAMES.index("average_risk")] is None


def test_recommends_first_route() -> None:
    ranking = rank((_route("slow", travel_time_s=7200), _route("fast", travel_time_s=3600)))

    assert ranking.recommended_id == "fast"
    assert ranking.no_recommendation_reason is None


def test_recommendation_skips_blocked_route() -> None:
    blocked = _route("a", {NO_TRAVEL: 1})
    calm = _route("b", {SEVERE: 500}, average_risk=3)

    assert rank((blocked, calm)).recommended_id == "b"


def test_every_route_blocked_gives_no_recommendation() -> None:
    ranking = rank((_route("a", {NO_TRAVEL: 1}), _route("b", {NO_TRAVEL: 2})))

    assert ranking.order == ("a", "b")
    assert ranking.recommended_id is None
    assert ranking.no_recommendation_reason is NoRecommendationReason.EVERY_ROUTE_BLOCKED


def test_blocked_and_unknown_routes_give_every_route_blocked() -> None:
    ranking = rank((_route("a", average_risk=None), _route("b", {NO_TRAVEL: 2})))

    assert ranking.recommended_id is None
    assert ranking.no_recommendation_reason is NoRecommendationReason.EVERY_ROUTE_BLOCKED


def test_no_known_weather_gives_no_recommendation() -> None:
    ranking = rank((_route("a", average_risk=None), _route("b", average_risk=None)))

    assert ranking.recommended_id is None
    assert ranking.no_recommendation_reason is NoRecommendationReason.NO_KNOWN_WEATHER


def test_one_route() -> None:
    ranking = rank((_route("only", {HIGH: 3}),))

    assert ranking.order == ("only",)
    assert ranking.recommended_id == "only"
    assert ranking.keys[0].values == (0.0, 0.0, 3.0, 0.5, 3600.0)


def test_no_routes() -> None:
    ranking = rank(())

    assert ranking.order == ()
    assert ranking.recommended_id is None
    assert ranking.no_recommendation_reason is None


def test_a_rated_ferry_alone_is_not_known_weather() -> None:
    ferry_only = _route("ferry", {LOW: 10}, average_risk=0.0, weather_rated_km=0.0)
    rated = _route("rated", {HIGH: 50, LOW: 50}, average_risk=1.0)

    ranking = rank([ferry_only, rated])

    assert ranking.order == ("rated", "ferry")
    assert ranking.recommended_id == "rated"


def _with_unknown(route_id: str, low_km: float, unknown_km: float) -> RankingInput:
    base = _route(route_id, {LOW: low_km}, average_risk=0.0)
    summary = replace(base.summary, unknown_km=unknown_km, total_km=low_km + unknown_km)
    return replace(base, summary=summary)


def test_no_unknown_limit_recommends_the_mostly_unknown_route() -> None:
    mostly_unknown = _with_unknown("unknown", low_km=1, unknown_km=99)
    known_high = _route("known", {HIGH: 10, LOW: 90}, average_risk=0.2)

    ranking = rank([mostly_unknown, known_high], max_unknown_share=None)

    assert ranking.recommended_id == "unknown"
    assert ranking.not_recommendable == {}


def test_unknown_limit_skips_to_the_next_route_without_changing_the_order() -> None:
    mostly_unknown = _with_unknown("unknown", low_km=1, unknown_km=99)
    known_high = _route("known", {HIGH: 10, LOW: 90}, average_risk=0.2)

    ranking = rank([mostly_unknown, known_high], max_unknown_share=0.25)

    assert ranking.order == ("unknown", "known")
    assert ranking.recommended_id == "known"
    assert ranking.not_recommendable == {"unknown": NotRecommendableReason.TOO_MUCH_UNKNOWN_WEATHER}


@pytest.mark.parametrize(("unknown_km", "allowed"), [(25.0, True), (25.01, False)])
def test_unknown_share_exactly_at_the_limit_is_allowed(unknown_km: float, allowed: bool) -> None:
    route = _with_unknown("only", low_km=100 - unknown_km, unknown_km=unknown_km)

    ranking = rank([route], max_unknown_share=0.25)

    assert (ranking.recommended_id == "only") is allowed


def test_every_route_over_the_limit_gives_its_own_reason() -> None:
    routes = [_with_unknown("a", 10, 90), _with_unknown("b", 20, 80)]

    ranking = rank(routes, max_unknown_share=0.25)

    assert ranking.recommended_id is None
    assert ranking.no_recommendation_reason is NoRecommendationReason.TOO_MUCH_UNKNOWN_WEATHER


def test_blocked_and_too_unknown_routes_report_the_unknown_reason() -> None:
    blocked = _route("blocked", {NO_TRAVEL: 5, LOW: 95})
    too_unknown = _with_unknown("unknown", 10, 90)

    ranking = rank([blocked, too_unknown], max_unknown_share=0.25)

    assert ranking.recommended_id is None
    assert ranking.no_recommendation_reason is NoRecommendationReason.TOO_MUCH_UNKNOWN_WEATHER
    assert ranking.not_recommendable == {
        "blocked": NotRecommendableReason.BLOCKED,
        "unknown": NotRecommendableReason.TOO_MUCH_UNKNOWN_WEATHER,
    }
