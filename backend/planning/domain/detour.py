"""Via points for the detour round of the top-up (`docs/trip-planning.md`, "Reaching 3 routes")."""

from planning.constants import (
    DETOUR_MAX_OFFSET_KM,
    DETOUR_MIN_OFFSET_KM,
    DETOUR_OFFSET_ROUTE_SHARE,
    DETOUR_POSITION_ROUTE_SHARE,
)
from planning.domain.geometry import RouteLine, Side, offset_point
from planning.domain.values import Coordinate

DETOUR_SIDES = (Side.LEFT, Side.RIGHT)


def detour_offset_km(length_km: float) -> float:
    """How far sideways the via point goes: a share of the route's length, clamped."""
    return min(
        DETOUR_MAX_OFFSET_KM, max(DETOUR_MIN_OFFSET_KM, length_km * DETOUR_OFFSET_ROUTE_SHARE)
    )


def detour_vias(fastest: RouteLine) -> tuple[Coordinate, ...]:
    """Candidate via points in the order to try them: pushed sideways from the middle of the
    fastest route, on each side of `DETOUR_SIDES` in turn. Empty for a line with no length."""
    if fastest.length_km <= 0:
        return ()
    at_km = fastest.length_km * DETOUR_POSITION_ROUTE_SHARE
    offset_km = detour_offset_km(fastest.length_km)
    return tuple(offset_point(fastest, at_km, offset_km, side) for side in DETOUR_SIDES)
