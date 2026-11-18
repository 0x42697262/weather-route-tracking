"""Local checks shared by trip planning and the weather grid; each raises `InvalidRequest`
naming the field to change, before any outbound call."""

from datetime import datetime, timedelta

from planning import text
from planning.domain.risk_constants import FORECAST_WINDOW_HOURS
from planning.errors import InvalidRequest, PlanningError, Rejection, TripOptionsInvalid
from planning.keys import FIELD_DEPARTURE_UTC
from planning.services.constants import DEPARTURE_PAST_TOLERANCE, SECONDS_PER_MINUTE


def latest_departure_hours(forecast_horizon_hours: int) -> int:
    """How far ahead a departure may be so the whole window still has forecasts."""
    return max(0, forecast_horizon_hours - FORECAST_WINDOW_HOURS)


def check_departure(departure_utc: datetime, now_utc: datetime, horizon_hours: int) -> None:
    """The departure is not in the past beyond the tolerance, nor beyond the forecast range.

    Raises:
        InvalidRequest: on `departure_utc`.
    """
    if departure_utc < now_utc - DEPARTURE_PAST_TOLERANCE:
        tolerance_minutes = int(DEPARTURE_PAST_TOLERANCE.total_seconds() // SECONDS_PER_MINUTE)
        raise InvalidRequest(
            Rejection.DEPARTURE_OUT_OF_RANGE,
            FIELD_DEPARTURE_UTC,
            text.departure_in_past(tolerance_minutes),
        )
    ahead_hours = latest_departure_hours(horizon_hours)
    if departure_utc > now_utc + timedelta(hours=ahead_hours):
        raise InvalidRequest(
            Rejection.DEPARTURE_OUT_OF_RANGE,
            FIELD_DEPARTURE_UTC,
            text.departure_too_far(ahead_hours),
        )


def rejection_reason(error: PlanningError) -> str:
    """The reason logged when a request is rejected with `error`."""
    if isinstance(error, InvalidRequest):
        return error.reason.value
    if isinstance(error, TripOptionsInvalid):
        return Rejection.OPTIONS_INVALID.value
    return error.code.value
