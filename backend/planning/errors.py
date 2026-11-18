"""Named errors of planning, one class per failure family, each with its catalog code.

The API exception handler maps `code` to an HTTP status and a message (`core.api`).
"""

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    """Every error code the API can return."""

    INVALID_REQUEST = "invalid_request"
    NO_ROAD_ROUTE = "no_road_route"
    PLACE_NOT_FOUND = "place_not_found"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    UPSTREAM_BUSY = "upstream_busy"
    UPSTREAM_INVALID_RESPONSE = "upstream_invalid_response"
    NO_ACTIVE_RULE_SET = "no_active_rule_set"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True, slots=True)
class ErrorDetail:
    """One field-level problem attached to an error."""

    field: str
    message: str


class PlanningError(Exception):
    """Base of every named planning error. `details` lists field-level problems, if any."""

    code: ErrorCode = ErrorCode.INVALID_REQUEST
    details: tuple[ErrorDetail, ...] = ()


class Rejection(StrEnum):
    """Why a request was rejected before or between outbound calls; logged with `trip.rejected`."""

    OPTIONS_INVALID = "options_invalid"
    DEPARTURE_OUT_OF_RANGE = "departure_out_of_range"
    SAME_PLACE = "same_place"
    TRIP_TOO_LONG = "trip_too_long"
    TOO_MANY_CHECKPOINTS = "too_many_checkpoints"
    TOO_MANY_WEATHER_CELLS = "too_many_weather_cells"
    LINE_INVALID = "line_invalid"
    CORRIDOR_TOO_LARGE = "corridor_too_large"
    QUERY_TOO_SHORT = "query_too_short"


class InvalidRequest(PlanningError):
    """A request that is well formed but breaks a rule; `details` name the field to change."""

    code = ErrorCode.INVALID_REQUEST

    def __init__(self, reason: Rejection, field: str, message: str) -> None:
        """Keep the reason for the log and one detail for the driver."""
        super().__init__(reason, field)
        self.reason = reason
        self.details = (ErrorDetail(field=field, message=message),)


class RateLimited(PlanningError):
    """The client sent more requests than its per-minute limit."""

    code = ErrorCode.RATE_LIMITED


class TripOptionsInvalid(PlanningError):
    """One or more trip options are outside the option registry."""

    code = ErrorCode.INVALID_REQUEST

    def __init__(self, details: tuple[ErrorDetail, ...]) -> None:
        """Keep every problem."""
        super().__init__(details)
        self.details = details


class NoActiveRuleSet(PlanningError):
    """No rule set version is active, so nothing can be planned."""

    code = ErrorCode.NO_ACTIVE_RULE_SET


class NoRoadRoute(PlanningError):
    """The routing provider found no road link between the two points."""

    code = ErrorCode.NO_ROAD_ROUTE


class PlaceNotFound(PlanningError):
    """The place id is unknown to the geocoder."""

    code = ErrorCode.PLACE_NOT_FOUND


class UpstreamUnavailable(PlanningError):
    """A provider could not be reached, timed out, or failed after retries."""

    code = ErrorCode.UPSTREAM_UNAVAILABLE


class UpstreamBusy(PlanningError):
    """A provider kept answering 429 after retries."""

    code = ErrorCode.UPSTREAM_BUSY


class UpstreamInvalidResponse(PlanningError):
    """A provider answered with data that does not parse."""

    code = ErrorCode.UPSTREAM_INVALID_RESPONSE
