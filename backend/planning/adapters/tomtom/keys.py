"""Paths, query parameter names, header names and wire values of the TomTom APIs."""

from collections.abc import Mapping
from types import MappingProxyType

from planning.domain.values import Avoidance

ROUTE_PATH_TEMPLATE = "/routing/{version}/calculateRoute/{locations}/{content_type}"
ROUTE_LOCATION_SEPARATOR = ":"
COORDINATE_SEPARATOR = ","

PARAM_KEY = "key"
PARAM_TRAVEL_MODE = "travelMode"
PARAM_VEHICLE_WEIGHT = "vehicleWeight"
PARAM_VEHICLE_MAX_SPEED = "vehicleMaxSpeed"
PARAM_VEHICLE_COMMERCIAL = "vehicleCommercial"
PARAM_MAX_ALTERNATIVES = "maxAlternatives"
PARAM_ALTERNATIVE_TYPE = "alternativeType"
PARAM_AVOID = "avoid"
PARAM_DEPART_AT = "departAt"
PARAM_SECTION_TYPE = "sectionType"
PARAM_EXTENDED_ROUTE_REPRESENTATION = "extendedRouteRepresentation"
PARAM_ROUTE_REPRESENTATION = "routeRepresentation"

TRAVEL_MODE_TRUCK = "truck"
WIRE_TRUE = "true"
ALTERNATIVE_TYPE_ANY_ROUTE = "anyRoute"
SECTION_TYPE_FERRY = "ferry"
RESPONSE_SECTION_TYPE_FERRY = "FERRY"
EXTENDED_REPRESENTATIONS = ("travelTime", "distance")
ROUTE_REPRESENTATION_POLYLINE = "polyline"
DEPART_AT_TIMESPEC = "seconds"

AVOID_VALUES: Mapping[Avoidance, str] = MappingProxyType(
    {
        Avoidance.TOLL_ROADS: "tollRoads",
        Avoidance.MOTORWAYS: "motorways",
    },
)

NO_ROAD_ROUTE_ERROR_CODES = frozenset({"NO_ROUTE_FOUND", "MAP_MATCHING_FAILURE"})

SUGGEST_PATH = "/maps/orbis/places/suggest"
DETAILS_PATH_TEMPLATE = "/maps/orbis/places/details/areas/{place_id}"

HEADER_API_KEY = "TomTom-Api-Key"
HEADER_API_VERSION = "TomTom-Api-Version"
HEADER_ATTRIBUTES = "Attributes"
HEADER_SESSION_ID = "Session-Id"

BODY_QUERY = "query"
BODY_MAX_RESULTS = "maxResults"
BODY_FILTERS = "filters"
BODY_FILTER_TYPES = "types"

SUGGEST_ATTRIBUTES = "results(id,type,title,subtitles)"
DETAILS_ATTRIBUTES = "id,title,subtitles,position"
SUGGEST_RESULT_TYPE_AREA = "area"
SUBTITLE_SEPARATOR = ", "

OPERATION_ROUTES = "routes"
OPERATION_SUGGEST = "suggest"
OPERATION_DETAILS = "details"
