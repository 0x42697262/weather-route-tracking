"""Response schemas of `GET /api/v1/places` and `GET /api/v1/places/{id}` (the contract)."""

from ninja import Schema

from planning.domain.values import Place, PlaceSuggestion


class PlaceSuggestionOut(Schema):
    """One suggestion; picking it costs one details call."""

    id: str
    title: str
    subtitle: str


class PlaceSuggestionsOut(Schema):
    """Suggestions in the geocoder's order."""

    suggestions: list[PlaceSuggestionOut]


class PlaceOut(Schema):
    """A picked place: the label to show and send back with the trip, and its position."""

    id: str
    label: str
    latitude: float
    longitude: float


def suggestions_out(suggestions: tuple[PlaceSuggestion, ...]) -> PlaceSuggestionsOut:
    """The suggestions response."""
    return PlaceSuggestionsOut(
        suggestions=[
            PlaceSuggestionOut(id=item.place_id, title=item.title, subtitle=item.subtitle)
            for item in suggestions
        ]
    )


def place_out(place: Place) -> PlaceOut:
    """The details response."""
    return PlaceOut(
        id=place.place_id,
        label=place.label,
        latitude=place.coordinate.latitude,
        longitude=place.coordinate.longitude,
    )
