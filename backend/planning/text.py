"""Messages of planning: the API error catalog and option problems."""

from collections.abc import Mapping
from types import MappingProxyType

from planning.errors import ErrorCode

ERROR_MESSAGES: Mapping[ErrorCode, str] = MappingProxyType(
    {
        ErrorCode.INVALID_REQUEST: "The request is not valid. Check the listed fields.",
        ErrorCode.NO_ROAD_ROUTE: "There is no road route between these two places.",
        ErrorCode.PLACE_NOT_FOUND: "That place could not be found. Search for it again.",
        ErrorCode.UPSTREAM_UNAVAILABLE: (
            "A map or weather service is not answering. Try again in a few minutes."
        ),
        ErrorCode.UPSTREAM_BUSY: "A map or weather service is busy. Try again in a minute.",
        ErrorCode.UPSTREAM_INVALID_RESPONSE: (
            "A map or weather service sent data we could not read. Try again later."
        ),
        ErrorCode.NO_ACTIVE_RULE_SET: (
            "Trip planning is not configured yet: no rule set is active. Contact the staff."
        ),
        ErrorCode.RATE_LIMITED: "Too many requests. Wait a minute and try again.",
    },
)

SPACING_NOT_ALLOWED = "Choose one of the allowed checkpoint spacings."
OPTION_REQUIRED = "This option is required."
OPTION_UNAVAILABLE = "This option is not available yet."
NOT_A_FINITE_NUMBER = "Must be a finite number."


def out_of_bounds(minimum: float, maximum: float, unit: str) -> str:
    """Problem: a number outside its bounds, in the option's canonical unit."""
    return f"Must be between {minimum:g} {unit} and {maximum:g} {unit}."


def unit_not_allowed(allowed: list[str]) -> str:
    """Problem: a quantity sent in a unit of the wrong kind."""
    return f"Must be one of these units: {', '.join(allowed)}."


NOT_UTC_AWARE = "Must be a date and time with a time zone, for example 2026-11-18T14:00:00Z."


def departure_in_past(tolerance_minutes: int) -> str:
    """Problem: the departure is more than the tolerance in the past."""
    return (
        f"The departure is more than {tolerance_minutes} minutes in the past. "
        "Choose now or a later time."
    )


def departure_too_far(max_hours_ahead: int) -> str:
    """Problem: the departure is beyond the forecast range."""
    return (
        f"Weather forecasts reach only {max_hours_ahead} hours ahead for a full trip. "
        "Choose an earlier departure."
    )


SAME_PLACE = "The origin and the destination are the same place. Choose two different places."
TRIP_TOO_LONG = "This trip is longer than the longest trip the app plans. Choose closer places."


def too_many_checkpoints(count: int, cap: int) -> str:
    """Problem: the spacing puts more checkpoints on a route than allowed."""
    return (
        f"This spacing needs {count} checkpoints on a route, and at most {cap} are allowed. "
        "Choose a wider spacing."
    )


TOO_MANY_WEATHER_CELLS = (
    "This trip needs weather for more places than allowed. Choose a wider spacing."
)
POLYLINE_INVALID = "This route line is not a valid encoded polyline."
LINE_TOO_SHORT = "A route line needs at least two points."


def line_too_many_points(cap: int) -> str:
    """Problem: a route line has more points than allowed."""
    return f"A route line may have at most {cap} points."


LINE_TOO_LONG = "This route line is longer than the longest trip the app plans."
CORRIDOR_TOO_LARGE = "These route lines cover too large an area for the weather map."


def query_too_short(minimum: int) -> str:
    """Problem: a place search shorter than the minimum."""
    return f"Type at least {minimum} characters."


TOMTOM_ROUTING_ATTRIBUTION = "\u00a9TomTom"
TOMTOM_PLACES_ATTRIBUTION = "\u00a9TomTom, \u00a9OpenStreetMap"
OPEN_METEO_ATTRIBUTION = "Weather data by Open-Meteo.com"
FAKE_DATA_ATTRIBUTION = "Synthetic test data"
