import json
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import pytest
from django.test import AsyncClient, Client

from core.wiring import use_providers
from planning.errors import NoRoadRoute, UpstreamUnavailable
from planning.tests.api.conftest import fake_providers
from planning.tests.services.support import ScriptedRoutes
from rulesets.models import RuleSetVersion
from shared.units import KG_PER_POUND

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedASGIResponse as ApiResponse

TRIPS_URL = "/api/v1/trips"
GRID_URL = "/api/v1/weather-grid"
LOAD_LB = 40000
JSON = "application/json"


def departure(hours: float = 1.0) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def trip_body(**changes: object) -> dict[str, Any]:
    body: dict[str, Any] = {
        "origin": {"label": "Dallas, TX", "latitude": 32.7767, "longitude": -96.797},
        "destination": {"label": "Oklahoma City, OK", "latitude": 35.4676, "longitude": -97.5164},
        "departure_utc": departure(),
        "load_weight": {"value": LOAD_LB, "unit": "lb"},
        "checkpoint_spacing": {"value": 25, "unit": "mi"},
    }
    body.update(changes)
    return body


async def post(client: AsyncClient, url: str, body: dict[str, Any]) -> ApiResponse:
    return await client.post(url, data=json.dumps(body), content_type=JSON)


def detail_fields(response: ApiResponse) -> list[str]:
    return [item["field"] for item in response.json()["error"]["details"]]


@pytest.mark.django_db
async def test_a_trip_is_planned_with_three_routes(async_client: AsyncClient) -> None:
    response = await post(async_client, TRIPS_URL, trip_body())

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["rule_set_version"] == 1
    assert body["routes_found"] == body["routes_requested"] == 3
    assert body["fewer_routes_than_requested"] is False
    assert body["options_used"]["load_kg"] == pytest.approx(LOAD_LB * KG_PER_POUND)
    assert body["options_used"]["checkpoint_spacing_km"] == pytest.approx(40.2336)
    assert body["options_used"]["include_rest_stops"] is True
    assert [route["rank"] for route in body["routes"]] == [1, 2, 3]
    first = body["routes"][0]
    assert first["polyline"]
    assert len(first["positions_by_hour"]) == 49
    assert first["checkpoints"][0]["distance_km"] == 0
    assert set(first["checkpoints"][0]["values"]) == {"wind_speed", "rain_rate", "snowfall_rate"}
    assert first["stretches"][0]["start_km"] == 0
    assert set(first["summary"]["distance_km_by_level"]) == {
        "low",
        "moderate",
        "high",
        "severe",
        "no_travel",
    }
    assert body["ranking"]["key_names"] == [
        "no_travel_km",
        "severe_km",
        "high_km",
        "average_risk",
        "travel_time_s",
    ]
    has_recommendation = body["recommended_route_id"] is not None
    assert has_recommendation != (body["no_recommendation_reason"] is not None)
    assert response.headers["X-Request-ID"]


@pytest.mark.django_db
async def test_metric_input_is_accepted_and_echoed(async_client: AsyncClient) -> None:
    body = trip_body(
        load_weight={"value": 18, "unit": "t"},
        checkpoint_spacing={"value": 16.09344, "unit": "km"},
        include_rest_stops=False,
    )

    response = await post(async_client, TRIPS_URL, body)

    assert response.status_code == HTTPStatus.OK
    used = response.json()["options_used"]
    assert used == {
        "checkpoint_spacing_km": 16.09344,
        "include_rest_stops": False,
        "load_kg": 18000,
    }


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"departure_utc": "2026-11-18T14:00:00"}, "body.payload.departure_utc"),
        ({"load_weight": {"value": 10, "unit": "mi"}}, "body.payload.load_weight"),
        ({"checkpoint_spacing": {"value": 25, "unit": "lb"}}, "body.payload.checkpoint_spacing"),
        (
            {"origin": {"label": "X", "latitude": 91, "longitude": 0}},
            "body.payload.origin.latitude",
        ),
        ({"load_weight": None}, "body.payload.load_weight"),
    ],
)
@pytest.mark.django_db
async def test_schema_failures_are_invalid_requests(
    async_client: AsyncClient, changes: dict[str, Any], field: str
) -> None:
    response = await post(async_client, TRIPS_URL, trip_body(**changes))

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"]["code"] == "invalid_request"
    assert any(item.startswith(field) for item in detail_fields(response))


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        (
            {"destination": {"label": "Dallas", "latitude": 32.7767, "longitude": -96.797}},
            "destination",
        ),
        ({"departure_utc": departure(-2)}, "departure_utc"),
        ({"departure_utc": departure(200)}, "departure_utc"),
        ({"checkpoint_spacing": {"value": 30, "unit": "km"}}, "checkpoint_spacing"),
        ({"load_weight": {"value": 200000, "unit": "lb"}}, "load_weight"),
    ],
)
@pytest.mark.django_db
async def test_local_rule_failures_name_the_field(
    async_client: AsyncClient, changes: dict[str, Any], field: str
) -> None:
    routes = ScriptedRoutes([])
    with use_providers(fake_providers(routes=routes)):
        response = await post(async_client, TRIPS_URL, trip_body(**changes))

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert detail_fields(response) == [field]
    assert routes.requests == []


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (UpstreamUnavailable(), HTTPStatus.BAD_GATEWAY, "upstream_unavailable"),
        (NoRoadRoute(), HTTPStatus.UNPROCESSABLE_CONTENT, "no_road_route"),
    ],
)
@pytest.mark.django_db
async def test_upstream_failures_map_to_the_catalog(
    async_client: AsyncClient, error: Exception, status: HTTPStatus, code: str
) -> None:
    with use_providers(fake_providers(routes=ScriptedRoutes([error]))):
        response = await post(async_client, TRIPS_URL, trip_body())

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["details"] is None


@pytest.mark.django_db
async def test_the_weather_grid_is_built_for_the_trip_lines(async_client: AsyncClient) -> None:
    long_trip = trip_body(
        origin={"label": "Chicago", "latitude": 41.8781, "longitude": -87.6298},
        destination={"label": "Denver", "latitude": 39.7392, "longitude": -104.9903},
    )
    planned = (await post(async_client, TRIPS_URL, long_trip)).json()
    lines = [route["polyline"] for route in planned["routes"]]

    response = await post(
        async_client,
        GRID_URL,
        {
            "lines": lines,
            "departure_utc": departure(),
            "load_weight": {"value": 40000, "unit": "lb"},
        },
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    cell_count = len(body["latitudes"])
    assert 0 < cell_count <= 300
    assert len(body["longitudes"]) == cell_count
    assert len(body["hours_utc"]) == 49
    assert body["levels"] == ["low", "moderate", "high", "severe", "no_travel"]
    assert [layer["key"] for layer in body["layers"]] == [
        "risk",
        "wind_speed",
        "rain_rate",
        "snowfall_rate",
    ]
    risk = body["layers"][0]
    assert risk["values"] is None
    assert len(risk["levels"]) == cell_count
    assert all(len(levels) == 49 for levels in risk["levels"])
    assert len(body["layers"][1]["values"][0]) == 49
    assert len(response.content) < 600_000


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"lines": ["a", "b", "c", "d"]}, "body.payload.lines"),
        ({"lines": []}, "body.payload.lines"),
        ({"lines": ["~~~~"]}, "lines.0"),
    ],
)
@pytest.mark.django_db
async def test_weather_grid_validation_failures(
    async_client: AsyncClient, body: dict[str, Any], field: str
) -> None:
    full = {"departure_utc": departure(), "load_weight": {"value": 1, "unit": "kg"}, **body}

    response = await post(async_client, GRID_URL, full)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert any(item.startswith(field) for item in detail_fields(response))


@pytest.mark.django_db
def test_weather_grid_without_an_active_rule_set_is_a_catalog_error(client: Client) -> None:
    RuleSetVersion.objects.all().update(is_active=False)
    body = {
        "lines": ["_p~iF~ps|U_ulLnnqC"],
        "departure_utc": departure(),
        "load_weight": {"value": 1, "unit": "kg"},
    }

    response = client.post(GRID_URL, data=json.dumps(body), content_type=JSON)

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error"]["code"] == "no_active_rule_set"
