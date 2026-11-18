"""A deterministic, keyless `RouteProvider` that draws synthetic routes between any two points.

The fastest route is the straight line; the alternatives bow sideways and drive slower, so they
are distinct and rank differently. It supports no avoidances and no via points, so top-up rounds
are skipped; asking for fewer alternatives returns fewer routes.
"""

import itertools
import math
from dataclasses import dataclass

from planning.adapters.fake.constants import (
    FASTEST_BOW_SHARE,
    FASTEST_SPEED_KMH,
    NORTH_BOW_SHARE,
    NORTH_SPEED_KMH,
    ROUTE_MAX_ALTERNATIVES,
    ROUTE_MAX_POINTS,
    ROUTE_MIN_POINTS,
    ROUTE_POINT_SPACING_KM,
    SOUTH_BOW_SHARE,
    SOUTH_SPEED_KMH,
)
from planning.constants import QUARTER_TURN_DEG, SECONDS_PER_HOUR
from planning.domain.geometry import (
    destination_point,
    haversine_km,
    initial_bearing_deg,
    measure_line,
)
from planning.domain.values import (
    Avoidance,
    Coordinate,
    ProgressPoint,
    ProviderRoute,
    RouteRequest,
)


@dataclass(frozen=True, slots=True)
class _Shape:
    bow_share: float
    speed_kmh: float


SHAPES = (
    _Shape(FASTEST_BOW_SHARE, FASTEST_SPEED_KMH),
    _Shape(NORTH_BOW_SHARE, NORTH_SPEED_KMH),
    _Shape(SOUTH_BOW_SHARE, SOUTH_SPEED_KMH),
)


def _line(origin: Coordinate, destination: Coordinate, bow_share: float) -> tuple[Coordinate, ...]:
    straight_km = haversine_km(origin, destination)
    count = max(
        ROUTE_MIN_POINTS, min(ROUTE_MAX_POINTS, math.ceil(straight_km / ROUTE_POINT_SPACING_KM))
    )
    bearing_deg = initial_bearing_deg(origin, destination)
    bow_km = bow_share * straight_km
    points: list[Coordinate] = []
    for number in range(count + 1):
        share = number / count
        on_chord = Coordinate(
            latitude=origin.latitude + (destination.latitude - origin.latitude) * share,
            longitude=origin.longitude + (destination.longitude - origin.longitude) * share,
        )
        sideways_km = bow_km * math.sin(math.pi * share)
        points.append(
            destination_point(on_chord, bearing_deg - QUARTER_TURN_DEG, sideways_km)
            if sideways_km
            else on_chord
        )
    return tuple(points)


def synthetic_route(
    locations: tuple[Coordinate, ...], bow_share: float, speed_kmh: float
) -> ProviderRoute:
    """A route through the locations, each leg bowed sideways by `bow_share` of its length,
    driven at a constant speed."""
    points: list[Coordinate] = []
    for start, end in itertools.pairwise(locations):
        leg = _line(start, end, bow_share)
        points.extend(leg if not points else leg[1:])
    line = measure_line(points)
    seconds_per_km = SECONDS_PER_HOUR / speed_kmh
    progress = tuple(
        ProgressPoint(point_index=index, distance_km=km, elapsed_s=km * seconds_per_km)
        for index, km in enumerate(line.cumulative_km)
    )
    return ProviderRoute(
        points=line.points,
        distance_km=line.length_km,
        travel_time_s=line.length_km * seconds_per_km,
        progress=progress,
        ferry_sections=(),
    )


class FakeRouteProvider:
    """Synthetic truck routes (`RouteProvider`); never calls anything."""

    @property
    def supported_avoidances(self) -> frozenset[Avoidance]:
        """None: the avoidance rounds are skipped."""
        return frozenset()

    @property
    def supports_via(self) -> bool:
        """No: the detour round is skipped."""
        return False

    @property
    def max_alternatives(self) -> int:
        """Two alternatives besides the fastest route."""
        return ROUTE_MAX_ALTERNATIVES

    async def routes(self, request: RouteRequest) -> tuple[ProviderRoute, ...]:
        """The straight route, then up to `alternatives` bowed ones."""
        locations = (request.origin, *request.via, request.destination)
        count = 1 + min(request.alternatives, ROUTE_MAX_ALTERNATIVES)
        return tuple(
            synthetic_route(locations, shape.bow_share, shape.speed_kmh) for shape in SHAPES[:count]
        )

    async def aclose(self) -> None:
        """Nothing to close."""


def build_fake_route_provider() -> FakeRouteProvider:
    """The fake routing adapter."""
    return FakeRouteProvider()
