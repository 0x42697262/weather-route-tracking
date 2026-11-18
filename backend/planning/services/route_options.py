"""Find up to `ROUTES_TARGET` distinct routes: the provider's own alternatives first, then top-up
rounds from a table (`docs/trip-planning.md`, "Reaching 3 routes").

Requests run strictly one after another. A failing top-up request is skipped and logged; only
the first request's errors reach the caller.
"""

import dataclasses
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from planning import text
from planning.domain.checkpoints import checkpoint_count
from planning.domain.detour import detour_vias
from planning.domain.geometry import DegenerateLine, RouteLine, measure_line
from planning.domain.options import TripOptionName
from planning.domain.providers import RouteProvider
from planning.domain.route_distinct import KeptRoutes, is_distinct
from planning.domain.values import Avoidance, Coordinate, ProviderRoute, RouteRequest, RouteSource
from planning.errors import InvalidRequest, NoRoadRoute, PlanningError, Rejection
from planning.events import ROUTES_FETCHED, ROUTES_REJECTED, ROUTES_ROUND_SKIPPED
from planning.keys import FIELD_DESTINATION
from planning.services.constants import (
    MOTORWAY_ROUND_MAX_FASTEST_KM,
    ROUTES_TARGET,
    TOP_UP_ALTERNATIVES,
)

logger = logging.getLogger(__name__)

FIRST_ROUTE_SOURCE = RouteSource.FASTEST
FIRST_ROUND_OTHER_SOURCE = RouteSource.ALTERNATIVE
REJECTED_TOO_LONG = "too_long"
REJECTED_TOO_MANY_CHECKPOINTS = "too_many_checkpoints"
REJECTED_REQUEST_FAILED = "request_failed"
SKIPPED_UNSUPPORTED = "unsupported"
SKIPPED_FASTEST_TOO_LONG = "fastest_too_long"
SKIPPED_NO_VIA = "no_via_point"
SKIPPED_REQUEST_CAP = "request_cap"
LOG_SHARE_DECIMALS = 3


@dataclass(frozen=True, slots=True)
class TopUpRound:
    """One top-up round: what it avoids, whether it goes through detour via points, and the
    fastest-route length from which it is skipped (None: never)."""

    source: RouteSource
    avoid: frozenset[Avoidance]
    uses_via: bool
    skip_from_fastest_km: float | None


TOP_UP_ROUNDS: tuple[TopUpRound, ...] = (
    TopUpRound(
        source=RouteSource.AVOID_TOLLS,
        avoid=frozenset({Avoidance.TOLL_ROADS}),
        uses_via=False,
        skip_from_fastest_km=None,
    ),
    TopUpRound(
        source=RouteSource.AVOID_HIGHWAYS,
        avoid=frozenset({Avoidance.MOTORWAYS}),
        uses_via=False,
        skip_from_fastest_km=MOTORWAY_ROUND_MAX_FASTEST_KM,
    ),
    TopUpRound(
        source=RouteSource.DETOUR,
        avoid=frozenset(),
        uses_via=True,
        skip_from_fastest_km=None,
    ),
)


@dataclass(frozen=True, slots=True)
class RouteBounds:
    """Limits a kept route must meet: its length and its checkpoint count at the spacing."""

    max_distance_km: float
    spacing_km: float
    max_checkpoints: int


@dataclass(frozen=True, slots=True)
class KeptRoute:
    """A kept route, its measured line and how it was found."""

    route: ProviderRoute
    line: RouteLine
    source: RouteSource


@dataclass(frozen=True, slots=True)
class RouteSearch:
    """The kept routes (fastest first), the rounds that sent a request, and the extra requests."""

    routes: tuple[KeptRoute, ...]
    rounds_tried: tuple[RouteSource, ...]
    extra_requests: int


def _bound_problem(line: RouteLine, bounds: RouteBounds) -> str | None:
    if line.length_km > bounds.max_distance_km:
        return REJECTED_TOO_LONG
    if checkpoint_count(line.length_km, bounds.spacing_km) > bounds.max_checkpoints:
        return REJECTED_TOO_MANY_CHECKPOINTS
    return None


def _check_fastest(line: RouteLine, bounds: RouteBounds) -> None:
    problem = _bound_problem(line, bounds)
    if problem == REJECTED_TOO_LONG:
        raise InvalidRequest(Rejection.TRIP_TOO_LONG, FIELD_DESTINATION, text.TRIP_TOO_LONG)
    if problem == REJECTED_TOO_MANY_CHECKPOINTS:
        count = checkpoint_count(line.length_km, bounds.spacing_km)
        raise InvalidRequest(
            Rejection.TOO_MANY_CHECKPOINTS,
            TripOptionName.CHECKPOINT_SPACING,
            text.too_many_checkpoints(count, bounds.max_checkpoints),
        )


class _Search:
    def __init__(self, provider: RouteProvider, provider_name: str, bounds: RouteBounds) -> None:
        self.provider = provider
        self.provider_name = provider_name
        self.bounds = bounds
        self.index = KeptRoutes()
        self.kept: list[KeptRoute] = []
        self.rounds_tried: list[RouteSource] = []
        self.extra_requests = 0

    @property
    def full(self) -> bool:
        return len(self.kept) >= ROUTES_TARGET

    def keep(self, route: ProviderRoute, line: RouteLine, source: RouteSource) -> None:
        self.index.add(line.points)
        self.kept.append(KeptRoute(route=route, line=line, source=source))

    def consider(self, route: ProviderRoute, source: RouteSource) -> None:
        if self.full:
            return
        line = measure_line(route.points)
        problem = _bound_problem(line, self.bounds)
        if problem is not None:
            self.reject(source, problem)
            return
        fastest_s = self.kept[0].route.travel_time_s
        decision = is_distinct(line.points, route.travel_time_s, self.index, fastest_s)
        if decision.reason is not None:
            self.reject(
                source,
                decision.reason.value,
                overlap_share=round(decision.overlap_share, LOG_SHARE_DECIMALS),
                time_ratio=round(decision.time_ratio, LOG_SHARE_DECIMALS),
            )
            return
        self.keep(route, line, source)

    def reject(self, source: RouteSource, reason: str, **measures: object) -> None:
        logger.info(ROUTES_REJECTED, extra={"round": source.value, "reason": reason, **measures})

    def fetched(self, source: RouteSource, count: int) -> None:
        logger.info(
            ROUTES_FETCHED,
            extra={"count": count, "provider": self.provider_name, "round": source.value},
        )

    def skipped(self, source: RouteSource, reason: str) -> None:
        logger.info(ROUTES_ROUND_SKIPPED, extra={"round": source.value, "reason": reason})


def _supported(top_up: TopUpRound, provider: RouteProvider) -> bool:
    return top_up.avoid <= provider.supported_avoidances and (
        not top_up.uses_via or provider.supports_via
    )


def _via_sets(top_up: TopUpRound, fastest: RouteLine) -> tuple[tuple[Coordinate, ...], ...]:
    if not top_up.uses_via:
        return ((),)
    try:
        return tuple((via,) for via in detour_vias(fastest))
    except DegenerateLine:
        return ()


def _skip_reason(top_up: TopUpRound, search: _Search, fastest: RouteLine) -> str | None:
    if not _supported(top_up, search.provider):
        return SKIPPED_UNSUPPORTED
    limit_km = top_up.skip_from_fastest_km
    if limit_km is not None and fastest.length_km >= limit_km:
        return SKIPPED_FASTEST_TOO_LONG
    return None


async def _run_round(
    top_up: TopUpRound, search: _Search, base: RouteRequest, max_extra_requests: int
) -> None:
    fastest = search.kept[0].line
    reason = _skip_reason(top_up, search, fastest)
    via_sets = _via_sets(top_up, fastest) if reason is None else ()
    if reason is None and not via_sets:
        reason = SKIPPED_NO_VIA
    if reason is not None:
        search.skipped(top_up.source, reason)
        return
    for via in via_sets:
        if search.full:
            return
        if search.extra_requests >= max_extra_requests:
            search.skipped(top_up.source, SKIPPED_REQUEST_CAP)
            return
        search.extra_requests += 1
        if top_up.source not in search.rounds_tried:
            search.rounds_tried.append(top_up.source)
        request = dataclasses.replace(
            base, alternatives=TOP_UP_ALTERNATIVES, avoid=top_up.avoid, via=via
        )
        try:
            answered = await search.provider.routes(request)
        except PlanningError as error:
            search.reject(top_up.source, REJECTED_REQUEST_FAILED, error=error.code.value)
            continue
        search.fetched(top_up.source, len(answered))
        for route in answered:
            search.consider(route, top_up.source)


async def find_routes(  # noqa: PLR0913
    provider: RouteProvider,
    provider_name: str,
    base: RouteRequest,
    bounds: RouteBounds,
    *,
    alternatives_requested: int,
    max_extra_requests: int,
    rounds: Sequence[TopUpRound] = TOP_UP_ROUNDS,
) -> RouteSearch:
    """Up to `ROUTES_TARGET` distinct routes, the fastest first.

    The first request asks for `alternatives_requested` alternatives (at most the provider's
    maximum); its first route is the fastest, the others are alternatives. While fewer than the
    target are kept, each supported round in `rounds` runs, until `max_extra_requests` extra
    requests were sent. `base` gives the trip; its alternatives, avoidances and via points are
    replaced per request.

    Raises:
        InvalidRequest: the fastest route is longer than allowed, or needs too many checkpoints.
        NoRoadRoute: the first request found no route.
        UpstreamUnavailable, UpstreamBusy, UpstreamInvalidResponse: from the first
            request.
    """
    search = _Search(provider, provider_name, bounds)
    first = dataclasses.replace(
        base,
        alternatives=min(alternatives_requested, provider.max_alternatives),
        avoid=frozenset(),
        via=(),
    )
    search.rounds_tried.append(FIRST_ROUTE_SOURCE)
    answered = await provider.routes(first)
    search.fetched(FIRST_ROUTE_SOURCE, len(answered))
    if not answered:
        raise NoRoadRoute
    fastest, *others = answered
    fastest_line = measure_line(fastest.points)
    _check_fastest(fastest_line, bounds)
    search.keep(fastest, fastest_line, FIRST_ROUTE_SOURCE)
    for route in others:
        search.consider(route, FIRST_ROUND_OTHER_SOURCE)
    for top_up in rounds:
        if search.full:
            break
        await _run_round(top_up, search, base, max_extra_requests)
    return RouteSearch(
        routes=tuple(search.kept),
        rounds_tried=tuple(search.rounds_tried),
        extra_requests=search.extra_requests,
    )
