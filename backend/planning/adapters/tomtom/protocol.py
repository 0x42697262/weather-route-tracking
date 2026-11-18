"""Pure request building and response parsing for TomTom Calculate Route and Places Search.

Parsing turns vendor JSON into metric domain objects and raises `UpstreamInvalidResponse` for
anything that does not match. Behavior of the vendor is described in `docs/facts.md` (F-43, F-44,
F-47, F-50, F-54) and `docs/trip-planning.md`.
"""

from collections.abc import Sequence
from datetime import UTC
from itertools import pairwise
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from planning.adapters.tomtom.constants import (
    COORDINATE_DECIMALS,
    MAX_ALTERNATIVES,
    ROUTING_API_VERSION,
    ROUTING_CONTENT_TYPE,
    SUGGEST_MAX_RESULTS,
)
from planning.adapters.tomtom.keys import (
    ALTERNATIVE_TYPE_ANY_ROUTE,
    AVOID_VALUES,
    BODY_FILTER_TYPES,
    BODY_FILTERS,
    BODY_MAX_RESULTS,
    BODY_QUERY,
    COORDINATE_SEPARATOR,
    DEPART_AT_TIMESPEC,
    DETAILS_PATH_TEMPLATE,
    EXTENDED_REPRESENTATIONS,
    NO_ROAD_ROUTE_ERROR_CODES,
    PARAM_ALTERNATIVE_TYPE,
    PARAM_AVOID,
    PARAM_DEPART_AT,
    PARAM_EXTENDED_ROUTE_REPRESENTATION,
    PARAM_KEY,
    PARAM_MAX_ALTERNATIVES,
    PARAM_ROUTE_REPRESENTATION,
    PARAM_SECTION_TYPE,
    PARAM_TRAVEL_MODE,
    PARAM_VEHICLE_COMMERCIAL,
    PARAM_VEHICLE_MAX_SPEED,
    PARAM_VEHICLE_WEIGHT,
    RESPONSE_SECTION_TYPE_FERRY,
    ROUTE_LOCATION_SEPARATOR,
    ROUTE_PATH_TEMPLATE,
    ROUTE_REPRESENTATION_POLYLINE,
    SECTION_TYPE_FERRY,
    SUBTITLE_SEPARATOR,
    SUGGEST_RESULT_TYPE_AREA,
    TRAVEL_MODE_TRUCK,
    WIRE_TRUE,
)
from planning.constants import MAX_LATITUDE_DEG, MAX_LONGITUDE_DEG
from planning.domain.values import (
    Coordinate,
    Place,
    PlaceSuggestion,
    PointRange,
    ProgressPoint,
    ProviderRoute,
    RouteRequest,
)
from planning.errors import UpstreamInvalidResponse
from shared.units import Unit, convert

type QueryParams = list[tuple[str, str | int | float | bool | None]]


class _VendorModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, frozen=True, extra="ignore"
    )


class _Point(_VendorModel):
    latitude: float = Field(ge=-MAX_LATITUDE_DEG, le=MAX_LATITUDE_DEG)
    longitude: float = Field(ge=-MAX_LONGITUDE_DEG, le=MAX_LONGITUDE_DEG)


class _Leg(_VendorModel):
    points: tuple[_Point, ...] = Field(min_length=1)


class _Summary(_VendorModel):
    length_in_meters: float = Field(ge=0)
    travel_time_in_seconds: float = Field(ge=0)


class _Progress(_VendorModel):
    point_index: int = Field(ge=0)
    travel_time_in_seconds: float = Field(ge=0)
    distance_in_meters: float = Field(ge=0)


class _Section(_VendorModel):
    start_point_index: int = Field(ge=0)
    end_point_index: int = Field(ge=0)
    section_type: str


class _Route(_VendorModel):
    summary: _Summary
    legs: tuple[_Leg, ...] = Field(min_length=1)
    sections: tuple[_Section, ...] = ()
    progress: tuple[_Progress, ...] = ()


class _RouteResponse(_VendorModel):
    routes: tuple[_Route, ...] = Field(min_length=1)


class _DetailedError(_VendorModel):
    code: str


class _ErrorResponse(_VendorModel):
    detailed_error: _DetailedError


class _Suggestion(_VendorModel):
    id: str | None = None
    type: str
    title: str = Field(min_length=1)
    subtitles: tuple[str, ...] = ()


class _SuggestResponse(_VendorModel):
    results: tuple[_Suggestion, ...]


class _Position(_VendorModel):
    coordinates: tuple[float, float]


class _PlaceDetails(_VendorModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    subtitles: tuple[str, ...] = ()
    position: _Position


def _format_coordinate(coordinate: Coordinate) -> str:
    return (
        f"{coordinate.latitude:.{COORDINATE_DECIMALS}f}"
        f"{COORDINATE_SEPARATOR}"
        f"{coordinate.longitude:.{COORDINATE_DECIMALS}f}"
    )


def route_path(request: RouteRequest) -> str:
    """The Calculate Route path: origin, via points in order, destination."""
    locations = (request.origin, *request.via, request.destination)
    return ROUTE_PATH_TEMPLATE.format(
        version=ROUTING_API_VERSION,
        locations=ROUTE_LOCATION_SEPARATOR.join(_format_coordinate(item) for item in locations),
        content_type=ROUTING_CONTENT_TYPE,
    )


def route_query(request: RouteRequest, api_key: str) -> QueryParams:
    """The Calculate Route query for a truck request, in metric units and UTC.

    Raises:
        ValueError: the departure is not timezone-aware.
    """
    if request.departure_utc.tzinfo is None:
        message = "departure_utc must be timezone-aware"
        raise ValueError(message)
    params: QueryParams = [
        (PARAM_KEY, api_key),
        (PARAM_TRAVEL_MODE, TRAVEL_MODE_TRUCK),
        (PARAM_VEHICLE_WEIGHT, str(round(request.vehicle.weight_kg))),
    ]
    if request.vehicle.max_speed_kmh is not None:
        params.append((PARAM_VEHICLE_MAX_SPEED, str(round(request.vehicle.max_speed_kmh))))
    params.extend(
        [
            (PARAM_VEHICLE_COMMERCIAL, WIRE_TRUE),
            (PARAM_MAX_ALTERNATIVES, str(min(request.alternatives, MAX_ALTERNATIVES))),
            (PARAM_ALTERNATIVE_TYPE, ALTERNATIVE_TYPE_ANY_ROUTE),
        ],
    )
    params.extend(
        (PARAM_AVOID, value) for value in sorted(AVOID_VALUES[item] for item in request.avoid)
    )
    params.extend(
        [
            (
                PARAM_DEPART_AT,
                request.departure_utc.astimezone(UTC).isoformat(timespec=DEPART_AT_TIMESPEC),
            ),
            (PARAM_SECTION_TYPE, SECTION_TYPE_FERRY),
        ],
    )
    params.extend(
        (PARAM_EXTENDED_ROUTE_REPRESENTATION, value) for value in EXTENDED_REPRESENTATIONS
    )
    params.append((PARAM_ROUTE_REPRESENTATION, ROUTE_REPRESENTATION_POLYLINE))
    return params


def error_code(payload: object) -> str | None:
    """The `detailedError.code` of an error body, or None when the body has none."""
    try:
        return _ErrorResponse.model_validate(payload).detailed_error.code
    except ValidationError:
        return None


def is_no_road_route(payload: object) -> bool:
    """Whether an error body says there is no road link between the points."""
    return error_code(payload) in NO_ROAD_ROUTE_ERROR_CODES


def _invalid() -> UpstreamInvalidResponse:
    return UpstreamInvalidResponse()


def _validate[ModelT: BaseModel](model: type[ModelT], payload: object) -> ModelT:
    try:
        return model.model_validate(payload)
    except ValidationError:
        raise _invalid() from None


def _merge_legs(legs: Sequence[_Leg]) -> tuple[tuple[Coordinate, ...], tuple[int, ...]]:
    """The route line with each leg joint once, and the merged index of every vendor index."""
    points: list[Coordinate] = []
    index_map: list[int] = []
    for leg_number, leg in enumerate(legs):
        for point_number, point in enumerate(leg.points):
            coordinate = Coordinate(latitude=point.latitude, longitude=point.longitude)
            repeats_joint = leg_number > 0 and point_number == 0 and points[-1] == coordinate
            if not repeats_joint:
                points.append(coordinate)
            index_map.append(len(points) - 1)
    return tuple(points), tuple(index_map)


def _km(meters: float) -> float:
    return convert(meters, Unit.METERS, Unit.KILOMETERS)


def _merged_index(index_map: Sequence[int], vendor_index: int) -> int:
    if vendor_index >= len(index_map):
        raise _invalid()
    return index_map[vendor_index]


def _progress(
    route: _Route, index_map: Sequence[int], last_index: int
) -> tuple[ProgressPoint, ...]:
    by_index: dict[int, ProgressPoint] = {}
    for entry in route.progress:
        merged = _merged_index(index_map, entry.point_index)
        by_index.setdefault(
            merged,
            ProgressPoint(
                point_index=merged,
                distance_km=_km(entry.distance_in_meters),
                elapsed_s=entry.travel_time_in_seconds,
            ),
        )
    by_index.setdefault(0, ProgressPoint(point_index=0, distance_km=0.0, elapsed_s=0.0))
    by_index.setdefault(
        last_index,
        ProgressPoint(
            point_index=last_index,
            distance_km=_km(route.summary.length_in_meters),
            elapsed_s=route.summary.travel_time_in_seconds,
        ),
    )
    ordered = tuple(by_index[index] for index in sorted(by_index))
    for previous, current in pairwise(ordered):
        if current.distance_km < previous.distance_km or current.elapsed_s < previous.elapsed_s:
            raise _invalid()
    return ordered


def _ferry_sections(route: _Route, index_map: Sequence[int]) -> tuple[PointRange, ...]:
    ranges: list[PointRange] = []
    for section in route.sections:
        if section.section_type != RESPONSE_SECTION_TYPE_FERRY:
            continue
        start = _merged_index(index_map, section.start_point_index)
        end = _merged_index(index_map, section.end_point_index)
        if end < start:
            raise _invalid()
        ranges.append(PointRange(start_index=start, end_index=end))
    return tuple(sorted(ranges, key=lambda item: item.start_index))


def _route(route: _Route) -> ProviderRoute:
    points, index_map = _merge_legs(route.legs)
    last_index = len(points) - 1
    return ProviderRoute(
        points=points,
        distance_km=_km(route.summary.length_in_meters),
        travel_time_s=route.summary.travel_time_in_seconds,
        progress=_progress(route, index_map, last_index),
        ferry_sections=_ferry_sections(route, index_map),
    )


def parse_routes(payload: object) -> tuple[ProviderRoute, ...]:
    """The routes of a Calculate Route body, in the vendor's order (fastest first).

    Raises:
        UpstreamInvalidResponse: the body does not describe valid routes.
    """
    response = _validate(_RouteResponse, payload)
    return tuple(_route(route) for route in response.routes)


def suggest_body(query: str) -> dict[str, Any]:
    """The Places Suggest body: the query, the result limit and areas only."""
    return {
        BODY_QUERY: query,
        BODY_MAX_RESULTS: SUGGEST_MAX_RESULTS,
        BODY_FILTERS: {BODY_FILTER_TYPES: [SUGGEST_RESULT_TYPE_AREA]},
    }


def parse_suggestions(payload: object) -> tuple[PlaceSuggestion, ...]:
    """The area suggestions of a Suggest body, in the vendor's order.

    Raises:
        UpstreamInvalidResponse: the body does not match.
    """
    response = _validate(_SuggestResponse, payload)
    return tuple(
        PlaceSuggestion(
            place_id=result.id,
            title=result.title,
            subtitle=SUBTITLE_SEPARATOR.join(result.subtitles),
        )
        for result in response.results
        if result.id and result.type == SUGGEST_RESULT_TYPE_AREA
    )


def details_path(place_id: str) -> str:
    """The Details path of an area, with the id escaped as one path segment."""
    return DETAILS_PATH_TEMPLATE.format(place_id=quote(place_id, safe=""))


def parse_place(payload: object) -> Place:
    """The place of a Details body; GeoJSON positions are `[longitude, latitude]`.

    Raises:
        UpstreamInvalidResponse: the body does not match or the position is out of range.
    """
    details = _validate(_PlaceDetails, payload)
    longitude, latitude = details.position.coordinates
    if abs(latitude) > MAX_LATITUDE_DEG or abs(longitude) > MAX_LONGITUDE_DEG:
        raise _invalid()
    return Place(
        place_id=details.id,
        label=SUBTITLE_SEPARATOR.join((details.title, *details.subtitles)),
        coordinate=Coordinate(latitude=latitude, longitude=longitude),
    )
