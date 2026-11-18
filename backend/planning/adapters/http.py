"""Outbound HTTP helpers shared by every adapter: the client factory, a call-rate limiter and
retries with exponential backoff, jitter, a cap and `Retry-After`.

Retries apply only to reads. A response is retried on a status in `RETRYABLE_STATUSES` and on
timeouts or connection errors; any other response is returned for the adapter to interpret.
"""

import asyncio
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from planning.adapters.constants import (
    BUSY_STATUSES,
    RETRY_AFTER_MAX_S,
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_BASE,
    RETRY_BASE_DELAY_S,
    RETRY_MAX_DELAY_S,
    RETRYABLE_STATUSES,
)
from planning.adapters.events import UPSTREAM_FAILED, UPSTREAM_RETRY
from planning.adapters.keys import RETRY_AFTER_HEADER, TRANSPORT_LOGGER_NAME
from planning.errors import UpstreamBusy, UpstreamUnavailable

logger = logging.getLogger(__name__)

type Sleep = Callable[[float], Awaitable[None]]
type Clock = Callable[[], float]
type Jitter = Callable[[float], float]
type Send = Callable[[], Awaitable[httpx.Response]]

_random = secrets.SystemRandom()


def full_jitter(ceiling_s: float) -> float:
    """A uniformly random delay between 0 and `ceiling_s`."""
    return _random.uniform(0, ceiling_s)


def quiet_transport_logs() -> None:
    """Stop httpx from logging request URLs at INFO; some vendor URLs carry an API key."""
    logging.getLogger(TRANSPORT_LOGGER_NAME).setLevel(logging.WARNING)


def build_http_client(
    base_url: str,
    connect_timeout_s: float,
    read_timeout_s: float,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """One async client for one provider, with timeouts on every phase of a call."""
    quiet_transport_logs()
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(read_timeout_s, connect=connect_timeout_s),
        transport=transport,
    )


@dataclass(slots=True)
class RateLimiter:
    """Spaces call starts so at most `max_calls_per_s` start per second.

    One instance shared by every client of a vendor API makes the limit process-wide.
    """

    max_calls_per_s: float
    clock: Clock = time.monotonic
    sleep: Sleep = asyncio.sleep
    _next_start_s: float = field(default=float("-inf"), init=False)

    async def acquire(self) -> None:
        """Wait until the next call may start, and reserve that start."""
        now_s = self.clock()
        start_s = max(now_s, self._next_start_s)
        self._next_start_s = start_s + 1 / self.max_calls_per_s
        delay_s = start_s - now_s
        if delay_s > 0:
            await self.sleep(delay_s)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """How often and how long to retry. `attempts` counts the first call."""

    attempts: int = RETRY_ATTEMPTS
    base_delay_s: float = RETRY_BASE_DELAY_S
    max_delay_s: float = RETRY_MAX_DELAY_S
    max_retry_after_s: float = RETRY_AFTER_MAX_S


def retry_after_s(response: httpx.Response, now_utc: datetime) -> float | None:
    """The delay a `Retry-After` header asks for, in seconds, or None when absent or invalid."""
    value = response.headers.get(RETRY_AFTER_HEADER)
    if value is None:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        pass
    try:
        retry_at = parsedate_to_datetime(value)
    except TypeError, ValueError:
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    return max((retry_at - now_utc).total_seconds(), 0.0)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Retrier:
    """Sends one read with the retry policy and an optional rate limiter.

    Raises:
        UpstreamBusy: the provider still answered 429 after the last attempt.
        UpstreamUnavailable: timeouts, connection errors or 5xx after the last attempt.
    """

    provider: str
    policy: RetryPolicy = field(default_factory=RetryPolicy)
    limiter: RateLimiter | None = None
    sleep: Sleep = asyncio.sleep
    jitter: Jitter = full_jitter
    utc_now: Callable[[], datetime] = _utc_now

    async def send(self, operation: str, send: Send) -> httpx.Response:
        """The first response that is not retryable; see the class for errors."""
        for attempt in range(1, self.policy.attempts + 1):
            is_last = attempt == self.policy.attempts
            if self.limiter is not None:
                await self.limiter.acquire()
            try:
                response = await send()
            except httpx.TransportError as error:
                if is_last:
                    self._log_failure(operation, attempt, type(error).__name__)
                    raise UpstreamUnavailable from None
                await self._wait(operation, attempt, type(error).__name__, None)
                continue
            if response.status_code not in RETRYABLE_STATUSES:
                return response
            requested_s = retry_after_s(response, self.utc_now())
            too_long = requested_s is not None and requested_s > self.policy.max_retry_after_s
            if is_last or too_long:
                self._log_failure(operation, attempt, str(response.status_code))
                if response.status_code in BUSY_STATUSES:
                    raise UpstreamBusy
                raise UpstreamUnavailable
            await self._wait(operation, attempt, str(response.status_code), requested_s)
        raise UpstreamUnavailable

    def backoff_s(self, attempt: int) -> float:
        """The jittered delay after a failed attempt (1-based)."""
        ceiling_s = min(
            self.policy.max_delay_s,
            self.policy.base_delay_s * RETRY_BACKOFF_BASE ** (attempt - 1),
        )
        return self.jitter(ceiling_s)

    async def _wait(
        self, operation: str, attempt: int, reason: str, requested_s: float | None
    ) -> None:
        delay_s = requested_s if requested_s is not None else self.backoff_s(attempt)
        logger.warning(
            UPSTREAM_RETRY,
            extra={
                "provider": self.provider,
                "operation": operation,
                "attempt": attempt,
                "reason": reason,
                "delay_s": round(delay_s, 3),
            },
        )
        await self.sleep(delay_s)

    def _log_failure(self, operation: str, attempt: int, reason: str) -> None:
        logger.warning(
            UPSTREAM_FAILED,
            extra={
                "provider": self.provider,
                "operation": operation,
                "attempts": attempt,
                "reason": reason,
            },
        )
