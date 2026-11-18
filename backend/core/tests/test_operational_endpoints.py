from http import HTTPStatus

import pytest
from django.test import AsyncClient, Client

from core.readiness import CheckStatus, ReadinessCheck, check_readiness
from rulesets.models import RuleSetVersion


async def test_health_answers_without_the_database(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/health")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
async def test_ready_reports_each_check(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/ready")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"ready": True, "checks": {"database": "ok", "rule_set": "ok"}}


@pytest.mark.django_db
def test_ready_fails_without_an_active_rule_set(client: Client) -> None:
    RuleSetVersion.objects.all().update(is_active=False)

    response = client.get("/api/ready")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {"ready": False, "checks": {"database": "ok", "rule_set": "failed"}}


async def _passes() -> bool:
    return True


async def _fails() -> bool:
    return False


async def test_a_failing_check_makes_the_process_not_ready() -> None:
    report = await check_readiness({ReadinessCheck.DATABASE: _fails})

    assert report.is_ready is False
    assert report.checks == {ReadinessCheck.DATABASE: CheckStatus.FAILED}


async def test_passing_checks_make_the_process_ready() -> None:
    report = await check_readiness({ReadinessCheck.DATABASE: _passes})

    assert report.is_ready is True


async def test_openapi_document_is_served(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/openapi.json")

    assert response.status_code == HTTPStatus.OK
    assert set(response.json()["paths"]) == {
        "/api/health",
        "/api/ready",
        "/api/v1/options",
        "/api/v1/trips",
        "/api/v1/weather-grid",
        "/api/v1/places",
        "/api/v1/places/{place_id}",
    }
