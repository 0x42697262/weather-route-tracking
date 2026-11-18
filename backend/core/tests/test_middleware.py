import json
import logging
import uuid
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import AsyncClient, RequestFactory

from core.constants import PLACES_RATE_LIMIT_PER_MINUTE
from core.middleware import client_address
from core.request_context import RequestIdFilter, current_request_id

TRIPS_URL = "/api/v1/trips"
PLACES_URL = "/api/v1/places"
HEALTH_URL = "/api/health"
GRID_URL = "/api/v1/weather-grid"
DETAILS_URL = "/api/v1/places/fake-dallas"


@pytest.fixture(autouse=True)
def empty_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


async def test_a_valid_request_id_is_echoed(async_client: AsyncClient) -> None:
    response = await async_client.get(HEALTH_URL, headers={"X-Request-ID": "abc-123"})

    assert response.headers["X-Request-ID"] == "abc-123"


async def test_an_invalid_request_id_is_replaced(async_client: AsyncClient) -> None:
    response = await async_client.get(HEALTH_URL, headers={"X-Request-ID": "bad id\n"})

    assert response.headers["X-Request-ID"] != "bad id\n"
    assert len(response.headers["X-Request-ID"]) == len(uuid.uuid4().hex)


def test_log_records_carry_the_request_id() -> None:
    record = logging.LogRecord("test", logging.INFO, "", 0, "event", None, None)
    token = current_request_id.set("req-1")
    try:
        RequestIdFilter().filter(record)
    finally:
        current_request_id.reset(token)

    assert record.__dict__["request_id"] == "req-1"


async def test_trips_over_the_limit_get_the_catalog_429(async_client: AsyncClient) -> None:
    limit = settings.APP_ENV.rate_limit_trips_per_minute
    statuses = []
    for _ in range(limit + 1):
        response = await async_client.post(TRIPS_URL, data="{}", content_type="application/json")
        statuses.append(response.status_code)

    assert HTTPStatus.TOO_MANY_REQUESTS not in statuses[:limit]
    assert statuses[-1] == HTTPStatus.TOO_MANY_REQUESTS
    assert json.loads(response.content)["error"]["code"] == "rate_limited"
    places = await async_client.get(PLACES_URL, {"query": "Da"})
    assert places.status_code == HTTPStatus.BAD_REQUEST


async def test_the_weather_grid_has_the_trip_limit_counted_on_its_own(
    async_client: AsyncClient,
) -> None:
    limit = settings.APP_ENV.rate_limit_trips_per_minute
    for _ in range(limit):
        await async_client.post(TRIPS_URL, data="{}", content_type="application/json")
    statuses = []
    for _ in range(limit + 1):
        response = await async_client.post(GRID_URL, data="{}", content_type="application/json")
        statuses.append(response.status_code)

    assert HTTPStatus.TOO_MANY_REQUESTS not in statuses[:limit]
    assert statuses[-1] == HTTPStatus.TOO_MANY_REQUESTS


async def test_places_and_details_share_the_places_limit(async_client: AsyncClient) -> None:
    statuses = []
    for _ in range(PLACES_RATE_LIMIT_PER_MINUTE):
        response = await async_client.get(PLACES_URL, {"query": "Da"})
        statuses.append(response.status_code)
    details = await async_client.get(DETAILS_URL)

    assert HTTPStatus.TOO_MANY_REQUESTS not in statuses
    assert details.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert json.loads(details.content)["error"]["code"] == "rate_limited"


async def test_other_paths_are_not_limited(async_client: AsyncClient) -> None:
    for _ in range(settings.APP_ENV.rate_limit_trips_per_minute + 1):
        response = await async_client.get(HEALTH_URL)

    assert response.status_code == HTTPStatus.OK


def test_the_client_address_is_the_last_forwarded_entry_behind_a_proxy() -> None:
    request = RequestFactory().get(
        TRIPS_URL, headers={"X-Forwarded-For": "203.0.113.9, 198.51.100.7"}
    )

    assert settings.APP_ENV.behind_proxy is True
    assert client_address(request) == "198.51.100.7"


def test_without_a_forwarded_header_the_peer_is_used() -> None:
    request = RequestFactory().get(TRIPS_URL, REMOTE_ADDR="192.0.2.4")

    assert client_address(request) == "192.0.2.4"
