"""A deterministic, keyless `Geocoder` over a small table of cities."""

from dataclasses import dataclass

from planning.adapters.fake.text import PLACES_SUBTITLE_SEPARATOR
from planning.domain.values import Coordinate, Place, PlaceSuggestion
from planning.errors import PlaceNotFound


@dataclass(frozen=True, slots=True)
class FakePlace:
    """One city of the table."""

    place_id: str
    title: str
    subtitle: str
    coordinate: Coordinate


FAKE_PLACES: tuple[FakePlace, ...] = (
    FakePlace("fake-dallas", "Dallas", "TX, United States", Coordinate(32.7767, -96.797)),
    FakePlace(
        "fake-oklahoma-city", "Oklahoma City", "OK, United States", Coordinate(35.4676, -97.5164)
    ),
    FakePlace("fake-houston", "Houston", "TX, United States", Coordinate(29.7604, -95.3698)),
    FakePlace("fake-austin", "Austin", "TX, United States", Coordinate(30.2672, -97.7431)),
    FakePlace("fake-denver", "Denver", "CO, United States", Coordinate(39.7392, -104.9903)),
    FakePlace("fake-chicago", "Chicago", "IL, United States", Coordinate(41.8781, -87.6298)),
)
PLACES_BY_ID = {place.place_id: place for place in FAKE_PLACES}


class FakeGeocoder:
    """Suggestions whose title contains the query, ignoring case (`Geocoder`)."""

    async def suggest(self, query: str, session_id: str) -> tuple[PlaceSuggestion, ...]:  # noqa: ARG002
        """Every table city whose title contains the query."""
        needle = query.strip().casefold()
        return tuple(
            PlaceSuggestion(place_id=place.place_id, title=place.title, subtitle=place.subtitle)
            for place in FAKE_PLACES
            if needle in place.title.casefold()
        )

    async def details(self, place_id: str) -> Place:
        """The city's coordinates.

        Raises:
            PlaceNotFound: the id is not in the table.
        """
        place = PLACES_BY_ID.get(place_id)
        if place is None:
            raise PlaceNotFound
        return Place(
            place_id=place.place_id,
            label=PLACES_SUBTITLE_SEPARATOR.join((place.title, place.subtitle)),
            coordinate=place.coordinate,
        )

    async def aclose(self) -> None:
        """Nothing to close."""


def build_fake_geocoder() -> FakeGeocoder:
    """The fake place search adapter."""
    return FakeGeocoder()
