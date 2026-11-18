"""Rank routes and pick the recommendation (`docs/risk-model.md` step 5).

The ranking keys are a table built from `RISK_LEVELS`: one distance per ranked level from the
highest score down, then the average risk, then travel time. Smaller is better.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from planning.domain.risk_constants import (
    AVERAGE_RISK_KEY,
    LEVEL_DISTANCE_KEY_SUFFIX,
    RANKING_AVERAGE_RISK_DECIMALS,
    RANKING_DISTANCE_DECIMALS,
    RANKING_TRAVEL_TIME_DECIMALS,
    TRAVEL_TIME_KEY,
    UNKNOWN_SHARE_DECIMALS,
)
from planning.domain.summary import RouteSummary
from shared.risk_levels import LEVELS_BY_SCORE, RISK_LEVELS, RiskLevel


@dataclass(frozen=True, slots=True)
class RankingInput:
    """One route to rank. `travel_time_s` is the full elapsed time, rest included."""

    route_id: str
    summary: RouteSummary
    travel_time_s: float


@dataclass(frozen=True, slots=True)
class RankingKey:
    """One entry of the ranking key: its name, how to read it, and its rounding."""

    name: str
    read: Callable[[RankingInput], float | None]
    decimals: int


class NoRecommendationReason(StrEnum):
    """Why no route is recommended."""

    EVERY_ROUTE_BLOCKED = "every_route_blocked"
    NO_KNOWN_WEATHER = "no_known_weather"
    TOO_MUCH_UNKNOWN_WEATHER = "too_much_unknown_weather"


class NotRecommendableReason(StrEnum):
    """Why one route cannot be recommended, in the order they are checked."""

    NO_KNOWN_WEATHER = "no_known_weather"
    BLOCKED = "blocked"
    TOO_MUCH_UNKNOWN_WEATHER = "too_much_unknown_weather"


@dataclass(frozen=True, slots=True)
class RouteKey:
    """A route's rounded ranking key.

    Attributes:
        route_id: the route.
        values: one value per entry of `RANKING_KEYS`, rounded; the average risk is None when the
            route has no known distance.
        has_known_weather: the route has distance with a level.
    """

    route_id: str
    values: tuple[float | None, ...]
    has_known_weather: bool


@dataclass(frozen=True, slots=True)
class Ranking:
    """Routes in ranked order and the recommendation.

    With at least one route, exactly one of `recommended_id` and `no_recommendation_reason` is
    set. With no routes, both are None. `not_recommendable` names, per route that cannot be
    recommended, the first reason that applies.
    """

    order: tuple[str, ...]
    keys: tuple[RouteKey, ...]
    recommended_id: str | None
    no_recommendation_reason: NoRecommendationReason | None
    not_recommendable: Mapping[str, NotRecommendableReason]


def _level_distance(level: RiskLevel) -> Callable[[RankingInput], float | None]:
    def read(route: RankingInput) -> float | None:
        return route.summary.distance_km_by_level[level]

    return read


def _average_risk(route: RankingInput) -> float | None:
    return route.summary.average_risk


def _travel_time_s(route: RankingInput) -> float | None:
    return route.travel_time_s


RANKING_KEYS: tuple[RankingKey, ...] = (
    *(
        RankingKey(
            name=f"{level}{LEVEL_DISTANCE_KEY_SUFFIX}",
            read=_level_distance(level),
            decimals=RANKING_DISTANCE_DECIMALS,
        )
        for level in reversed(LEVELS_BY_SCORE)
        if RISK_LEVELS[level].ranked
    ),
    RankingKey(AVERAGE_RISK_KEY, _average_risk, RANKING_AVERAGE_RISK_DECIMALS),
    RankingKey(TRAVEL_TIME_KEY, _travel_time_s, RANKING_TRAVEL_TIME_DECIMALS),
)
RANKING_KEY_NAMES: tuple[str, ...] = tuple(key.name for key in RANKING_KEYS)


def _rounded(value: float | None, decimals: int) -> float | None:
    return None if value is None else round(value, decimals) + 0.0


def route_key(route: RankingInput) -> RouteKey:
    """The route's rounded ranking key."""
    return RouteKey(
        route_id=route.route_id,
        values=tuple(_rounded(key.read(route), key.decimals) for key in RANKING_KEYS),
        has_known_weather=_has_known_weather(route),
    )


def _sort_key(key: RouteKey) -> tuple[bool, tuple[float, ...]]:
    filled = tuple(0.0 if value is None else value for value in key.values)
    return (not key.has_known_weather, filled)


def _has_known_weather(route: RankingInput) -> bool:
    return round(route.summary.weather_rated_km, RANKING_DISTANCE_DECIMALS) > 0


def _unknown_share(route: RankingInput) -> float:
    total_km = route.summary.total_km
    return route.summary.unknown_km / total_km if total_km > 0 else 0.0


def _exceeds_unknown_limit(route: RankingInput, max_unknown_share: float | None) -> bool:
    if max_unknown_share is None:
        return False
    return round(_unknown_share(route), UNKNOWN_SHARE_DECIMALS) > max_unknown_share


ROUTE_EXCLUSIONS: tuple[
    tuple[NotRecommendableReason, Callable[[RankingInput, float | None], bool]], ...
] = (
    (NotRecommendableReason.NO_KNOWN_WEATHER, lambda route, _limit: not _has_known_weather(route)),
    (NotRecommendableReason.BLOCKED, lambda route, _limit: route.summary.blocked),
    (NotRecommendableReason.TOO_MUCH_UNKNOWN_WEATHER, _exceeds_unknown_limit),
)

NO_RECOMMENDATION_BY_ROUTE_REASON: Mapping[NotRecommendableReason, NoRecommendationReason] = (
    MappingProxyType(
        {
            NotRecommendableReason.NO_KNOWN_WEATHER: NoRecommendationReason.NO_KNOWN_WEATHER,
            NotRecommendableReason.BLOCKED: NoRecommendationReason.EVERY_ROUTE_BLOCKED,
            NotRecommendableReason.TOO_MUCH_UNKNOWN_WEATHER: (
                NoRecommendationReason.TOO_MUCH_UNKNOWN_WEATHER
            ),
        },
    )
)


def not_recommendable_reason(
    route: RankingInput, max_unknown_share: float | None
) -> NotRecommendableReason | None:
    """The first reason in `ROUTE_EXCLUSIONS` order that applies to the route, or None."""
    return next(
        (reason for reason, applies in ROUTE_EXCLUSIONS if applies(route, max_unknown_share)),
        None,
    )


def rank(routes: Sequence[RankingInput], max_unknown_share: float | None = None) -> Ranking:
    """Sort routes by their rounded key, smallest first, and pick the recommendation.

    A route with no known distance sorts after every route with some. Routes whose keys are all
    equal keep their input order. The recommendation is the first route in that order that no
    exclusion in `ROUTE_EXCLUSIONS` applies to; `max_unknown_share` (None: no limit) is the
    largest share of a route's length with no forecast that a recommended route may have.

    Without a recommendation, the reason is the latest exclusion in `ROUTE_EXCLUSIONS` order that
    stopped a route with known weather, so the driver hears the most specific cause:
    `no_known_weather` when no route has known weather, `too_much_unknown_weather` when some
    unblocked route was stopped only by the Unknown limit, otherwise `every_route_blocked`.
    """
    by_id = {route.route_id: route for route in routes}
    keys = tuple(sorted((route_key(route) for route in routes), key=_sort_key))
    order = tuple(key.route_id for key in keys)
    exclusions = {
        route.route_id: not_recommendable_reason(route, max_unknown_share) for route in routes
    }
    recommended = next((route_id for route_id in order if exclusions[route_id] is None), None)
    return Ranking(
        order=order,
        keys=keys,
        recommended_id=recommended,
        no_recommendation_reason=(
            _reason([exclusions[route.route_id] for route in by_id.values()])
            if recommended is None
            else None
        ),
        not_recommendable=MappingProxyType(
            {route_id: reason for route_id, reason in exclusions.items() if reason is not None}
        ),
    )


def _reason(exclusions: Sequence[NotRecommendableReason | None]) -> NoRecommendationReason | None:
    if not exclusions:
        return None
    ordered = [reason for reason, _ in ROUTE_EXCLUSIONS]
    latest = max(
        (reason for reason in exclusions if reason is not None),
        key=ordered.index,
        default=None,
    )
    return None if latest is None else NO_RECOMMENDATION_BY_ROUTE_REASON[latest]
