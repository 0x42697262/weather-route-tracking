"""Place suggestions and details, passed through from the geocoder. Nothing is cached (TomTom
terms, `docs/facts.md` F-52)."""

from planning import text
from planning.domain.providers import Geocoder
from planning.domain.values import Place, PlaceSuggestion
from planning.errors import InvalidRequest, Rejection
from planning.keys import FIELD_QUERY
from planning.services.constants import PLACES_QUERY_MIN_CHARS


async def suggest_places(
    geocoder: Geocoder, query: str, session_id: str
) -> tuple[PlaceSuggestion, ...]:
    """Suggestions for a typed query of at least `PLACES_QUERY_MIN_CHARS` characters.

    Raises:
        InvalidRequest: the query is shorter once trimmed; the geocoder is not called.
        UpstreamUnavailable, UpstreamBusy, UpstreamInvalidResponse: see `planning.errors`.
    """
    trimmed = query.strip()
    if len(trimmed) < PLACES_QUERY_MIN_CHARS:
        raise InvalidRequest(
            Rejection.QUERY_TOO_SHORT, FIELD_QUERY, text.query_too_short(PLACES_QUERY_MIN_CHARS)
        )
    return await geocoder.suggest(trimmed, session_id)


async def place_details(geocoder: Geocoder, place_id: str) -> Place:
    """The coordinates of a picked suggestion.

    Raises:
        PlaceNotFound: the id is unknown.
        UpstreamUnavailable, UpstreamBusy, UpstreamInvalidResponse: see `planning.errors`.
    """
    return await geocoder.details(place_id)
