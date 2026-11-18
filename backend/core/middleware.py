"""Request middleware: a request id on every request and log line, and per-client rate limits
on the endpoints that call providers (`docs/architecture.md`, Request path)."""

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus

from asgiref.sync import markcoroutinefunction
from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponseBase, JsonResponse

from core.constants import PLACES_RATE_LIMIT_PER_MINUTE, RATE_LIMIT_WINDOW_S
from core.events import REQUEST_RATE_LIMITED
from core.keys import (
    FORWARDED_FOR_HEADER,
    FORWARDED_FOR_SEPARATOR,
    REMOTE_ADDR_META,
    REQUEST_ID_HEADER,
    REQUEST_ID_PATTERN,
    rate_limit_cache_key,
    v1_path,
)
from core.request_context import current_request_id
from core.schemas import ErrorBodyOut, ErrorOut
from planning.errors import ErrorCode
from planning.keys import PLACES_PATH, TRIPS_PATH, WEATHER_GRID_PATH
from planning.text import ERROR_MESSAGES

logger = logging.getLogger(__name__)

type GetResponse = Callable[[HttpRequest], Awaitable[HttpResponseBase]]

UNKNOWN_CLIENT = "unknown"


class RateScope(StrEnum):
    """Separately counted groups of endpoints."""

    TRIPS = "trips"
    WEATHER_GRID = "weather_grid"
    PLACES = "places"


@dataclass(frozen=True, slots=True)
class RateRule:
    """Which paths a scope covers (exact, or every path under a prefix) and its limit."""

    scope: RateScope
    path: str
    is_prefix: bool
    per_minute: Callable[[], int]

    def matches(self, path: str) -> bool:
        """Whether the request path falls under the rule."""
        return path.startswith(self.path) if self.is_prefix else path == self.path


def _trip_limit() -> int:
    limit: int = settings.APP_ENV.rate_limit_trips_per_minute
    return limit


RATE_RULES: tuple[RateRule, ...] = (
    RateRule(RateScope.TRIPS, v1_path(TRIPS_PATH), is_prefix=False, per_minute=_trip_limit),
    RateRule(
        RateScope.WEATHER_GRID, v1_path(WEATHER_GRID_PATH), is_prefix=False, per_minute=_trip_limit
    ),
    RateRule(
        RateScope.PLACES,
        v1_path(PLACES_PATH),
        is_prefix=True,
        per_minute=lambda: PLACES_RATE_LIMIT_PER_MINUTE,
    ),
)


def client_address(request: HttpRequest) -> str:
    """The client's address: the last `X-Forwarded-For` entry (the one our proxy added) when
    `BEHIND_PROXY`, otherwise the socket peer."""
    if settings.APP_ENV.behind_proxy:
        forwarded = request.headers.get(FORWARDED_FOR_HEADER, "")
        entries = [item.strip() for item in forwarded.split(FORWARDED_FOR_SEPARATOR)]
        if entries[-1]:
            return entries[-1]
    remote: str = request.META.get(REMOTE_ADDR_META) or UNKNOWN_CLIENT
    return remote


async def _count(key: str) -> int:
    if await cache.aadd(key, 1, timeout=RATE_LIMIT_WINDOW_S):
        return 1
    try:
        return await cache.aincr(key)
    except ValueError:
        await cache.aset(key, 1, timeout=RATE_LIMIT_WINDOW_S)
        return 1


def _rate_limited_response() -> JsonResponse:
    body = ErrorOut(
        error=ErrorBodyOut(
            code=ErrorCode.RATE_LIMITED,
            message=ERROR_MESSAGES[ErrorCode.RATE_LIMITED],
            details=None,
        )
    )
    return JsonResponse(body.model_dump(mode="json"), status=HTTPStatus.TOO_MANY_REQUESTS)


class RequestIdMiddleware:
    """Takes a valid `X-Request-ID` from the request or makes one, exposes it to logging for the
    request, and echoes it on the response."""

    async_capable = True
    sync_capable = False

    def __init__(self, get_response: GetResponse) -> None:
        """Wrap the next handler."""
        self.get_response = get_response
        markcoroutinefunction(self)

    async def __call__(self, request: HttpRequest) -> HttpResponseBase:
        """Serve the request under its id."""
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if re.fullmatch(REQUEST_ID_PATTERN, incoming) else uuid.uuid4().hex
        token = current_request_id.set(request_id)
        try:
            response = await self.get_response(request)
        finally:
            current_request_id.reset(token)
        response[REQUEST_ID_HEADER] = request_id
        return response


class RateLimitMiddleware:
    """Counts requests per client and scope in fixed one-minute windows in the cache; over the
    limit answers 429 with the catalog error."""

    async_capable = True
    sync_capable = False

    def __init__(self, get_response: GetResponse) -> None:
        """Wrap the next handler."""
        self.get_response = get_response
        markcoroutinefunction(self)

    async def __call__(self, request: HttpRequest) -> HttpResponseBase:
        """Pass the request on unless its client is over the limit of the path's scope."""
        rule = next((item for item in RATE_RULES if item.matches(request.path)), None)
        if rule is None:
            return await self.get_response(request)
        client = client_address(request)
        window = int(time.time() // RATE_LIMIT_WINDOW_S)
        count = await _count(rate_limit_cache_key(rule.scope, client, window))
        if count > rule.per_minute():
            logger.warning(REQUEST_RATE_LIMITED, extra={"scope": rule.scope, "count": count})
            return _rate_limited_response()
        return await self.get_response(request)
