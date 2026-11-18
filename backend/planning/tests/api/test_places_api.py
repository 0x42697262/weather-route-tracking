import uuid
from dataclasses import dataclass
from http import HTTPStatus

import pytest
from django.test import AsyncClient

from core.wiring import use_providers
from planning.domain.values import Place, PlaceSuggestion
from planning.errors import UpstreamBusy
from planning.tests.api.conftest import fake_providers

PLACES_URL = "/api/v1/places"
SESSION = str(uuid.uuid4())


@dataclass(slots=True)
class BusyGeocoder:
    calls: int = 0

    async def suggest(self, query: str, session_id: str) -> tuple[PlaceSuggestion, ...]:  # noqa: ARG002
        self.calls += 1
        raise UpstreamBusy

    async def details(self, place_id: str) -> Place:  # noqa: ARG002
        self.calls += 1
        raise UpstreamBusy


async def test_suggestions_for_a_query(async_client: AsyncClient) -> None:
    response = await async_client.get(PLACES_URL, {"query": "Dal", "session": SESSION})

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "suggestions": [{"id": "fake-dallas", "title": "Dallas", "subtitle": "TX, United States"}]
    }


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"query": "Da", "session": SESSION}, "query"),
        ({"query": "  Da  ", "session": SESSION}, "query"),
        ({"query": "Dallas", "session": "not-a-uuid"}, "query.session"),
        ({"query": "Dallas"}, "query.session"),
        ({"query": "D" * 101, "session": SESSION}, "query.query"),
    ],
)
async def test_bad_place_queries_are_rejected_without_a_call(
    async_client: AsyncClient, params: dict[str, str], field: str
) -> None:
    geocoder = BusyGeocoder()
    with use_providers(fake_providers(geocoder=geocoder)):
        response = await async_client.get(PLACES_URL, params)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    fields = [item["field"] for item in response.json()["error"]["details"]]
    assert fields == [field]
    assert geocoder.calls == 0


async def test_a_busy_geocoder_maps_to_the_catalog(async_client: AsyncClient) -> None:
    with use_providers(fake_providers(geocoder=BusyGeocoder())):
        response = await async_client.get(PLACES_URL, {"query": "Dallas", "session": SESSION})

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error"]["code"] == "upstream_busy"


async def test_place_details(async_client: AsyncClient) -> None:
    response = await async_client.get(f"{PLACES_URL}/fake-dallas")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": "fake-dallas",
        "label": "Dallas, TX, United States",
        "latitude": 32.7767,
        "longitude": -96.797,
    }


async def test_an_unknown_place_is_not_found(async_client: AsyncClient) -> None:
    response = await async_client.get(f"{PLACES_URL}/nowhere")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "place_not_found"


async def test_a_busy_geocoder_on_details_maps_to_the_catalog(async_client: AsyncClient) -> None:
    with use_providers(fake_providers(geocoder=BusyGeocoder())):
        response = await async_client.get(f"{PLACES_URL}/fake-dallas")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
