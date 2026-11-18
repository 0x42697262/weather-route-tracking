"""Fixed constants shared by every provider adapter: retries and HTTP status families.

The reasons for each value are in `docs/trip-planning.md` (Failure behavior) and
`docs/facts.md`.
"""

from http import HTTPStatus

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY_S = 0.5
RETRY_MAX_DELAY_S = 4.0
RETRY_AFTER_MAX_S = 10.0
RETRY_BACKOFF_BASE = 2

RETRYABLE_STATUSES = frozenset(
    {
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    },
)
BUSY_STATUSES = frozenset({HTTPStatus.TOO_MANY_REQUESTS})
