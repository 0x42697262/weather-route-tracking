"""Paths, API tags, request field names, ids, URLs and frontend text keys of planning."""

OPTIONS_PATH = "options"
TRIPS_PATH = "trips"
WEATHER_GRID_PATH = "weather-grid"
PLACES_PATH = "places"
PLACE_DETAILS_PATH = "places/{place_id}"
API_TAG = "planning"

CHECKPOINT_SPACING_TEXT_KEY = "checkpoint_spacing"
INCLUDE_REST_STOPS_TEXT_KEY = "include_rest_stops"
LOAD_WEIGHT_TEXT_KEY = "load_weight"
COMBINED_RISK_LAYER = "risk"
COMBINED_RISK_TEXT_KEY = "combined_risk"

FIELD_DEPARTURE_UTC = "departure_utc"
FIELD_DESTINATION = "destination"
FIELD_LINES = "lines"
FIELD_QUERY = "query"
FIELD_SEPARATOR = "."


def line_field(index: int) -> str:
    """The request field of one route line in a weather grid request."""
    return f"{FIELD_LINES}{FIELD_SEPARATOR}{index}"


def route_id(number: int) -> str:
    """The id of the kept route at a position (1 is the fastest)."""
    return f"route-{number}"


OPEN_METEO_ATTRIBUTION_URL = "https://open-meteo.com/"
