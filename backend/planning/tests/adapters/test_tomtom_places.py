import json
from collections.abc import AsyncIterator, Callable

import httpx
import pytest
from django.conf import settings

from planning.adapters.tomtom.client import TomTomGeocoder, build_tomtom_geocoder
from planning.adapters.tomtom.protocol import details_path
from planning.domain.values import Coordinate, Place, PlaceSuggestion
from planning.errors import PlaceNotFound, UpstreamInvalidResponse, UpstreamUnavailable
from planning.tests.adapters.support import (
    TEST_API_KEY,
    FakeTime,
    Recorder,
    fixture_text,
    make_retrier,
)

BASE_URL = "https://api.tomtom.example.com"
SESSION_ID = "0b9f1c52-5d3a-4c55-9a51-8a3f1f2f4b11"
DALLAS_ID = "zK2aykRFLfTtm0slSWcgUw"


@pytest.fixture
def fake_time() -> FakeTime:
    return FakeTime()


@pytest.fixture
async def make_geocoder(
    fake_time: FakeTime,
) -> AsyncIterator[Callable[[Recorder], TomTomGeocoder]]:
    clients: list[httpx.AsyncClient] = []

    def build(recorder: Recorder) -> TomTomGeocoder:
        client = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(recorder))
        clients.append(client)
        return TomTomGeocoder(client, TEST_API_KEY, make_retrier(fake_time))

    yield build
    for client in clients:
        await client.aclose()


async def test_suggest_posts_the_query_for_areas(
    make_geocoder: Callable[[Recorder], TomTomGeocoder],
) -> None:
    recorder = Recorder(httpx.Response(200, text=fixture_text("tomtom_suggest_dal.json")))

    suggestions = await make_geocoder(recorder).suggest("Dal", SESSION_ID)

    sent = recorder.requests[0]
    assert sent.method == "POST"
    assert sent.url.path == "/maps/orbis/places/suggest"
    assert sent.url.query == b""
    assert sent.headers["TomTom-Api-Key"] == TEST_API_KEY
    assert sent.headers["TomTom-Api-Version"] == "3"
    assert sent.headers["Attributes"] == "results(id,type,title,subtitles)"
    assert sent.headers["Session-Id"] == SESSION_ID
    assert json.loads(sent.content) == {
        "query": "Dal",
        "maxResults": 5,
        "filters": {"types": ["area"]},
    }
    assert len(suggestions) == 5
    assert suggestions[0] == PlaceSuggestion(
        place_id=DALLAS_ID, title="Dallas, TX", subtitle="United States"
    )
    assert suggestions[1].subtitle == "Taichung City, Taiwan"


async def test_suggest_skips_results_without_an_id_or_of_another_type(
    make_geocoder: Callable[[Recorder], TomTomGeocoder],
) -> None:
    body = {
        "results": [
            {"title": "Restaurant", "type": "discoverAction"},
            {"id": "poi-1", "title": "Diner", "type": "poi"},
            {"id": "area-1", "title": "Dalhart", "type": "area"},
        ]
    }
    recorder = Recorder(httpx.Response(200, json=body))

    suggestions = await make_geocoder(recorder).suggest("Dal", SESSION_ID)

    assert suggestions == (PlaceSuggestion(place_id="area-1", title="Dalhart", subtitle=""),)


async def test_suggest_malformed_is_invalid(
    make_geocoder: Callable[[Recorder], TomTomGeocoder],
) -> None:
    recorder = Recorder(httpx.Response(200, json={"items": []}))

    with pytest.raises(UpstreamInvalidResponse):
        await make_geocoder(recorder).suggest("Dal", SESSION_ID)


async def test_suggest_retries_503(
    make_geocoder: Callable[[Recorder], TomTomGeocoder], fake_time: FakeTime
) -> None:
    recorder = Recorder(
        httpx.Response(503), httpx.Response(200, text=fixture_text("tomtom_suggest_dal.json"))
    )

    suggestions = await make_geocoder(recorder).suggest("Dal", SESSION_ID)

    assert len(suggestions) == 5
    assert fake_time.sleeps == [0.5]


async def test_suggest_timeout_is_unavailable(
    make_geocoder: Callable[[Recorder], TomTomGeocoder],
) -> None:
    recorder = Recorder(*[httpx.ConnectTimeout("down")] * 3)

    with pytest.raises(UpstreamUnavailable):
        await make_geocoder(recorder).suggest("Dal", SESSION_ID)


async def test_details_reads_geojson_longitude_first(
    make_geocoder: Callable[[Recorder], TomTomGeocoder],
) -> None:
    recorder = Recorder(httpx.Response(200, text=fixture_text("tomtom_details_dallas.json")))

    place = await make_geocoder(recorder).details(DALLAS_ID)

    sent = recorder.requests[0]
    assert sent.method == "GET"
    assert sent.url.path == f"/maps/orbis/places/details/areas/{DALLAS_ID}"
    assert sent.headers["Attributes"] == "id,title,subtitles,position"
    assert sent.headers["TomTom-Api-Version"] == "3"
    assert "Session-Id" not in sent.headers
    assert place == Place(
        place_id=DALLAS_ID,
        label="Dallas, TX, United States",
        coordinate=Coordinate(latitude=32.777976, longitude=-96.796215),
    )


async def test_unknown_place_is_not_found(
    make_geocoder: Callable[[Recorder], TomTomGeocoder],
) -> None:
    recorder = Recorder(httpx.Response(404, text=fixture_text("tomtom_details_not_found.json")))

    with pytest.raises(PlaceNotFound):
        await make_geocoder(recorder).details("AAAAAAAAAAAAAAAAAAAAAA")

    assert len(recorder.requests) == 1


async def test_details_position_out_of_range_is_invalid(
    make_geocoder: Callable[[Recorder], TomTomGeocoder],
) -> None:
    body = {"id": "x", "title": "Nowhere", "position": {"coordinates": [10.0, 95.0]}}
    recorder = Recorder(httpx.Response(200, json=body))

    with pytest.raises(UpstreamInvalidResponse):
        await make_geocoder(recorder).details("x")


def test_details_path_escapes_the_id() -> None:
    assert details_path("a/b c") == "/maps/orbis/places/details/areas/a%2Fb%20c"


async def test_factory_builds_from_settings() -> None:
    recorder = Recorder(httpx.Response(200, text=fixture_text("tomtom_details_dallas.json")))
    geocoder = build_tomtom_geocoder(settings.APP_ENV, httpx.MockTransport(recorder))

    try:
        place = await geocoder.details(DALLAS_ID)
    finally:
        await geocoder.aclose()

    assert place.place_id == DALLAS_ID
    assert recorder.requests[0].url.host == settings.APP_ENV.tomtom_base_url.host
