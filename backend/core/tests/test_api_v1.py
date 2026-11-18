from http import HTTPStatus

import pytest
from django.test import AsyncClient, Client, RequestFactory
from ninja.errors import ValidationError

from core.api import ERROR_STATUS, on_planning_error, on_validation_error
from planning.errors import ErrorCode, ErrorDetail, TripOptionsInvalid, UpstreamBusy
from planning.text import ERROR_MESSAGES
from rulesets.models import RuleSetVersion

OPTIONS_URL = "/api/v1/options"


def test_every_error_code_has_a_status_and_a_message() -> None:
    assert set(ERROR_STATUS) == set(ErrorCode)
    assert set(ERROR_MESSAGES) == set(ErrorCode)


@pytest.mark.django_db
async def test_options_come_from_the_active_rule_set(async_client: AsyncClient) -> None:
    response = await async_client.get(OPTIONS_URL)

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["rule_set_version"] == 1
    assert body["forecast_window_hours"] == 48
    spacing = body["options"]["checkpoint_spacing"]
    assert [(choice["value"], choice["unit"]) for choice in spacing["choices"]] == [
        (10, "mi"),
        (25, "mi"),
        (50, "mi"),
    ]
    assert spacing["default"] == {"value": 25, "unit": "mi", "km": pytest.approx(40.2336)}
    assert spacing["tier"] == "basic"
    assert body["options"]["include_rest_stops"] == {
        "name": "include_rest_stops",
        "tier": "advanced",
        "text_key": "include_rest_stops",
        "available": True,
        "default": True,
    }
    assert body["stretch_method"] == "worse_end"
    assert body["routes_target"] == 3
    assert body["departure_window"] == {"past_tolerance_minutes": 15, "max_hours_ahead": 96}
    assert [notice["text"] for notice in body["attribution"]] == [
        "\u00a9TomTom",
        "\u00a9TomTom, \u00a9OpenStreetMap",
        "Weather data by Open-Meteo.com",
    ]
    load = body["options"]["load_weight"]
    assert (load["unit"], load["required"], load["minimum"]) == ("kg", True, 0)
    assert [level["key"] for level in body["risk_levels"]] == [
        "low",
        "moderate",
        "high",
        "severe",
        "no_travel",
    ]
    assert body["risk_levels"][-1] == {
        "key": "no_travel",
        "score": 4,
        "ranked": True,
        "blocks_recommendation": True,
        "text_key": "no_travel",
        "color_key": "risk-no-travel",
    }
    assert body["weather_variables"][0] == {
        "key": "wind_speed",
        "metric_unit": "km/h",
        "text_key": "wind_speed",
    }
    assert body["heatmap_layers"]["default"] == "risk"
    assert [layer["key"] for layer in body["heatmap_layers"]["layers"]] == [
        "risk",
        "wind_speed",
        "rain_rate",
        "snowfall_rate",
    ]


@pytest.mark.django_db
def test_options_without_an_active_rule_set_is_a_catalog_error(client: Client) -> None:
    RuleSetVersion.objects.all().update(is_active=False)

    response = client.get(OPTIONS_URL)

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {
        "error": {
            "code": "no_active_rule_set",
            "message": ERROR_MESSAGES[ErrorCode.NO_ACTIVE_RULE_SET],
            "details": None,
        }
    }


def test_a_named_error_with_details_lists_them() -> None:
    request = RequestFactory().get(OPTIONS_URL)
    error = TripOptionsInvalid((ErrorDetail(field="load_weight", message="Too heavy."),))

    response = on_planning_error(request, error)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert b'"details": [{"field": "load_weight", "message": "Too heavy."}]' in response.content


def test_a_named_error_maps_to_its_status() -> None:
    response = on_planning_error(RequestFactory().get(OPTIONS_URL), UpstreamBusy())

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert b'"code": "upstream_busy"' in response.content


def test_a_schema_failure_is_an_invalid_request_with_field_details() -> None:
    error = ValidationError(
        [{"loc": ("body", "payload", "load_weight"), "msg": "Field required", "type": "missing"}]
    )

    response = on_validation_error(RequestFactory().post(OPTIONS_URL), error)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert b'"code": "invalid_request"' in response.content
    assert b'"field": "body.payload.load_weight"' in response.content
