"""TomTom adapters: truck routing (`RouteProvider`) and Places Search (`Geocoder`).

Nothing they return is cached or stored (`docs/facts.md` F-52). The routing key travels as a
query parameter, so request URLs are never logged.
"""

import json
from http import HTTPStatus

import httpx

from core.env import AppEnv
from core.provider_names import GeocoderName, RouteProviderName
from planning.adapters.http import RateLimiter, Retrier, build_http_client
from planning.adapters.tomtom.constants import (
    MAX_ALTERNATIVES,
    PLACES_API_VERSION,
    PLACES_MAX_CALLS_PER_S,
    ROUTING_MAX_CALLS_PER_S,
)
from planning.adapters.tomtom.keys import (
    AVOID_VALUES,
    DETAILS_ATTRIBUTES,
    HEADER_API_KEY,
    HEADER_API_VERSION,
    HEADER_ATTRIBUTES,
    HEADER_SESSION_ID,
    OPERATION_DETAILS,
    OPERATION_ROUTES,
    OPERATION_SUGGEST,
    SUGGEST_ATTRIBUTES,
    SUGGEST_PATH,
)
from planning.adapters.tomtom.protocol import (
    details_path,
    is_no_road_route,
    parse_place,
    parse_routes,
    parse_suggestions,
    route_path,
    route_query,
    suggest_body,
)
from planning.adapters.tomtom.text import TOMTOM_API_KEY_MISSING
from planning.domain.values import Avoidance, Place, PlaceSuggestion, ProviderRoute, RouteRequest
from planning.errors import (
    NoRoadRoute,
    PlaceNotFound,
    UpstreamInvalidResponse,
    UpstreamUnavailable,
)

ROUTING_LIMITER = RateLimiter(max_calls_per_s=ROUTING_MAX_CALLS_PER_S)
PLACES_LIMITER = RateLimiter(max_calls_per_s=PLACES_MAX_CALLS_PER_S)


def _json(response: httpx.Response) -> object:
    try:
        payload: object = response.json()
    except json.JSONDecodeError, UnicodeDecodeError:
        raise UpstreamInvalidResponse from None
    return payload


def _json_or_none(response: httpx.Response) -> object:
    try:
        payload: object = response.json()
    except json.JSONDecodeError, UnicodeDecodeError:
        return None
    return payload


class TomTomRouteProvider:
    """Truck routes from TomTom Calculate Route (`RouteProvider`)."""

    def __init__(self, client: httpx.AsyncClient, api_key: str, retrier: Retrier) -> None:
        """Use `client` (base URL and timeouts set) and `retrier` (limiter included)."""
        self._client = client
        self._api_key = api_key
        self._retrier = retrier

    @property
    def supported_avoidances(self) -> frozenset[Avoidance]:
        """Toll roads and motorways."""
        return frozenset(AVOID_VALUES)

    @property
    def supports_via(self) -> bool:
        """Via points are sent as waypoints."""
        return True

    @property
    def max_alternatives(self) -> int:
        """TomTom computes at most 5 alternatives per request."""
        return MAX_ALTERNATIVES

    async def routes(self, request: RouteRequest) -> tuple[ProviderRoute, ...]:
        """The fastest route first, then the alternatives.

        Raises:
            NoRoadRoute: TomTom found no road link, or a point is not near a road.
            UpstreamBusy, UpstreamUnavailable, UpstreamInvalidResponse: see `planning.errors`.
        """
        path = route_path(request)
        params = route_query(request, self._api_key)
        response = await self._retrier.send(
            OPERATION_ROUTES, lambda: self._client.get(path, params=params)
        )
        if response.status_code == HTTPStatus.OK:
            return parse_routes(_json(response))
        if response.status_code == HTTPStatus.BAD_REQUEST and is_no_road_route(
            _json_or_none(response)
        ):
            raise NoRoadRoute
        raise UpstreamUnavailable

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


class TomTomGeocoder:
    """Place suggestions and coordinates from TomTom Places Search (`Geocoder`)."""

    def __init__(self, client: httpx.AsyncClient, api_key: str, retrier: Retrier) -> None:
        """Use `client` (base URL and timeouts set) and `retrier` (limiter included)."""
        self._client = client
        self._api_key = api_key
        self._retrier = retrier

    def _headers(self, attributes: str, session_id: str | None) -> dict[str, str]:
        headers = {
            HEADER_API_KEY: self._api_key,
            HEADER_API_VERSION: PLACES_API_VERSION,
            HEADER_ATTRIBUTES: attributes,
        }
        if session_id:
            headers[HEADER_SESSION_ID] = session_id
        return headers

    async def suggest(self, query: str, session_id: str) -> tuple[PlaceSuggestion, ...]:
        """Area suggestions for a partial query. `session_id` must be a UUID (v4 or v7).

        Raises:
            UpstreamBusy, UpstreamUnavailable, UpstreamInvalidResponse: see `planning.errors`.
        """
        headers = self._headers(SUGGEST_ATTRIBUTES, session_id)
        body = suggest_body(query)
        response = await self._retrier.send(
            OPERATION_SUGGEST,
            lambda: self._client.post(SUGGEST_PATH, headers=headers, json=body),
        )
        if response.status_code != HTTPStatus.OK:
            raise UpstreamUnavailable
        return parse_suggestions(_json(response))

    async def details(self, place_id: str) -> Place:
        """The coordinates and label of an area suggestion.

        Raises:
            PlaceNotFound: TomTom does not know the id.
            UpstreamBusy, UpstreamUnavailable, UpstreamInvalidResponse: see `planning.errors`.
        """
        headers = self._headers(DETAILS_ATTRIBUTES, None)
        path = details_path(place_id)
        response = await self._retrier.send(
            OPERATION_DETAILS, lambda: self._client.get(path, headers=headers)
        )
        if response.status_code == HTTPStatus.NOT_FOUND:
            raise PlaceNotFound
        if response.status_code != HTTPStatus.OK:
            raise UpstreamUnavailable
        return parse_place(_json(response))

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


def _api_key(env: AppEnv) -> str:
    if env.tomtom_api_key is None:
        raise ValueError(TOMTOM_API_KEY_MISSING)
    return env.tomtom_api_key.get_secret_value()


def _client(env: AppEnv, transport: httpx.AsyncBaseTransport | None) -> httpx.AsyncClient:
    return build_http_client(
        str(env.tomtom_base_url),
        env.http_connect_timeout_seconds,
        env.http_read_timeout_seconds,
        transport,
    )


def build_tomtom_route_provider(
    env: AppEnv, transport: httpx.AsyncBaseTransport | None = None
) -> TomTomRouteProvider:
    """The routing adapter from settings, sharing the process-wide routing limiter.

    Raises:
        ValueError: `TOMTOM_API_KEY` is not set.
    """
    return TomTomRouteProvider(
        _client(env, transport),
        _api_key(env),
        Retrier(provider=RouteProviderName.TOMTOM.value, limiter=ROUTING_LIMITER),
    )


def build_tomtom_geocoder(
    env: AppEnv, transport: httpx.AsyncBaseTransport | None = None
) -> TomTomGeocoder:
    """The place search adapter from settings, sharing the process-wide places limiter.

    Raises:
        ValueError: `TOMTOM_API_KEY` is not set.
    """
    return TomTomGeocoder(
        _client(env, transport),
        _api_key(env),
        Retrier(provider=GeocoderName.TOMTOM.value, limiter=PLACES_LIMITER),
    )
