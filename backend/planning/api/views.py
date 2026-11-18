"""Planning endpoints under `/api/v1/`. Thin: validate, call a service, return a schema."""

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from django.http import HttpRequest
from ninja import Path, Query, Router

from core.schemas import ErrorOut
from core.wiring import limits, providers
from planning.api.grid_schemas import (
    WeatherGridIn,
    WeatherGridOut,
    grid_request,
    weather_grid_out,
)
from planning.api.place_schemas import (
    PlaceOut,
    PlaceSuggestionsOut,
    place_out,
    suggestions_out,
)
from planning.api.schemas import OptionsOut, options_out
from planning.api.trip_schemas import TripIn, TripOut, trip_out, trip_request
from planning.domain.options import build_options
from planning.keys import (
    API_TAG,
    OPTIONS_PATH,
    PLACE_DETAILS_PATH,
    PLACES_PATH,
    TRIPS_PATH,
    WEATHER_GRID_PATH,
)
from planning.services.constants import (
    PLACE_ID_MAX_CHARS,
    PLACES_QUERY_MAX_CHARS,
)
from planning.services.places import place_details, suggest_places
from planning.services.plan_trip import plan_trip
from planning.services.weather_grid import build_weather_grid
from rulesets.services.active import get_active_rule_set

router = Router(tags=[API_TAG])

ERROR_RESPONSES: dict[int, type[ErrorOut]] = {
    HTTPStatus.BAD_REQUEST: ErrorOut,
    HTTPStatus.NOT_FOUND: ErrorOut,
    HTTPStatus.UNPROCESSABLE_CONTENT: ErrorOut,
    HTTPStatus.TOO_MANY_REQUESTS: ErrorOut,
    HTTPStatus.BAD_GATEWAY: ErrorOut,
    HTTPStatus.SERVICE_UNAVAILABLE: ErrorOut,
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


@router.get(OPTIONS_PATH, response={HTTPStatus.OK: OptionsOut, **ERROR_RESPONSES})
async def options(request: HttpRequest) -> OptionsOut:  # noqa: ARG001
    """What the driver may choose and the defaults, from the active rule set, plus the
    attribution of the chosen providers."""
    versioned = await get_active_rule_set()
    wired = providers()
    return options_out(
        versioned,
        build_options(versioned.rules),
        wired.attributions,
        wired.weather.forecast_horizon_hours,
    )


@router.post(TRIPS_PATH, response={HTTPStatus.OK: TripOut, **ERROR_RESPONSES})
async def trips(request: HttpRequest, payload: TripIn) -> TripOut:  # noqa: ARG001
    """Plan a trip: up to 3 routes with checkpoints, weather, risk and a recommendation."""
    wired = providers()
    plan = await plan_trip(
        trip_request(payload),
        routes=wired.routes,
        route_provider_name=wired.route_provider_name,
        weather=wired.weather,
        rule_set=await get_active_rule_set(),
        limits=limits(),
        now_utc=_utc_now(),
    )
    return trip_out(plan)


@router.post(WEATHER_GRID_PATH, response={HTTPStatus.OK: WeatherGridOut, **ERROR_RESPONSES})
async def weather_grid(request: HttpRequest, payload: WeatherGridIn) -> WeatherGridOut:  # noqa: ARG001
    """The heatmap grid around the given route lines for the whole forecast window."""
    result = await build_weather_grid(
        grid_request(payload),
        weather=providers().weather,
        rule_set=await get_active_rule_set(),
        limits=limits(),
        now_utc=_utc_now(),
    )
    return weather_grid_out(result)


@router.get(PLACES_PATH, response={HTTPStatus.OK: PlaceSuggestionsOut, **ERROR_RESPONSES})
async def places(
    request: HttpRequest,  # noqa: ARG001
    query: Annotated[str, Query(max_length=PLACES_QUERY_MAX_CHARS)],
    session: Annotated[UUID, Query()],
) -> PlaceSuggestionsOut:
    """Place suggestions for a typed query; `session` (a UUID) groups one typing session."""
    found = await suggest_places(providers().geocoder, query, str(session))
    return suggestions_out(found)


@router.get(PLACE_DETAILS_PATH, response={HTTPStatus.OK: PlaceOut, **ERROR_RESPONSES})
async def place(
    request: HttpRequest,  # noqa: ARG001
    place_id: Annotated[str, Path(max_length=PLACE_ID_MAX_CHARS)],
) -> PlaceOut:
    """The coordinates of a picked suggestion."""
    return place_out(await place_details(providers().geocoder, place_id))
