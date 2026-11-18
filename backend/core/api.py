"""The API: one Ninja instance mounted at `/api/`, with the operational endpoints, the versioned
routers under `/api/v1/` and the exception handlers that turn named errors into the catalog."""

from collections.abc import Mapping
from http import HTTPStatus
from types import MappingProxyType

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from ninja import NinjaAPI, Router, Status
from ninja.errors import ValidationError

from core.constants import API_VERSION
from core.keys import API_DOCS_PATH, API_URL_NAMESPACE, API_V1_PREFIX, HEALTH_PATH, READY_PATH
from core.readiness import check_readiness
from core.schemas import (
    ErrorBodyOut,
    ErrorDetailOut,
    ErrorOut,
    HealthOut,
    HealthStatus,
    ReadinessOut,
)
from core.text import API_TITLE
from planning.api.views import router as planning_router
from planning.errors import ErrorCode, PlanningError
from planning.text import ERROR_MESSAGES

ERROR_STATUS: Mapping[ErrorCode, HTTPStatus] = MappingProxyType(
    {
        ErrorCode.INVALID_REQUEST: HTTPStatus.BAD_REQUEST,
        ErrorCode.NO_ROAD_ROUTE: HTTPStatus.UNPROCESSABLE_CONTENT,
        ErrorCode.PLACE_NOT_FOUND: HTTPStatus.NOT_FOUND,
        ErrorCode.UPSTREAM_UNAVAILABLE: HTTPStatus.BAD_GATEWAY,
        ErrorCode.UPSTREAM_BUSY: HTTPStatus.SERVICE_UNAVAILABLE,
        ErrorCode.UPSTREAM_INVALID_RESPONSE: HTTPStatus.BAD_GATEWAY,
        ErrorCode.NO_ACTIVE_RULE_SET: HTTPStatus.SERVICE_UNAVAILABLE,
        ErrorCode.RATE_LIMITED: HTTPStatus.TOO_MANY_REQUESTS,
    },
)
LOCATION_SEPARATOR = "."

api = NinjaAPI(
    title=API_TITLE,
    version=API_VERSION,
    urls_namespace=API_URL_NAMESPACE,
    docs_url=API_DOCS_PATH if settings.DEBUG else None,
)

v1 = Router()
v1.add_router("", planning_router)
api.add_router(API_V1_PREFIX, v1)


def error_response(
    request: HttpRequest, code: ErrorCode, details: list[ErrorDetailOut] | None
) -> HttpResponse:
    """The catalog response for an error code: its status, message and details."""
    body = ErrorOut(error=ErrorBodyOut(code=code, message=ERROR_MESSAGES[code], details=details))
    return api.create_response(request, body.model_dump(mode="json"), status=ERROR_STATUS[code])


@api.exception_handler(PlanningError)
def on_planning_error(request: HttpRequest, error: PlanningError) -> HttpResponse:
    """A named error becomes its catalog response."""
    details = [ErrorDetailOut(field=item.field, message=item.message) for item in error.details]
    return error_response(request, error.code, details or None)


@api.exception_handler(ValidationError)
def on_validation_error(request: HttpRequest, error: ValidationError) -> HttpResponse:
    """A request that fails its schema becomes `invalid_request` with one detail per field."""
    details = [
        ErrorDetailOut(
            field=LOCATION_SEPARATOR.join(str(part) for part in problem.get("loc", ())),
            message=str(problem.get("msg", "")),
        )
        for problem in error.errors
    ]
    return error_response(request, ErrorCode.INVALID_REQUEST, details)


@api.get(HEALTH_PATH, response=HealthOut)
async def health(request: HttpRequest) -> HealthOut:  # noqa: ARG001
    """The process is up. Checks nothing else."""
    return HealthOut(status=HealthStatus.OK)


@api.get(
    READY_PATH, response={HTTPStatus.OK: ReadinessOut, HTTPStatus.SERVICE_UNAVAILABLE: ReadinessOut}
)
async def ready(request: HttpRequest) -> Status[ReadinessOut]:  # noqa: ARG001
    """The process can serve requests: the database is reachable and a rule set is active."""
    report = await check_readiness()
    status = HTTPStatus.OK if report.is_ready else HTTPStatus.SERVICE_UNAVAILABLE
    return Status(status, ReadinessOut(ready=report.is_ready, checks=dict(report.checks)))
