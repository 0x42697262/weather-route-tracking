import logging
from datetime import UTC, datetime

import httpx
import pytest

from planning.adapters.http import (
    RateLimiter,
    Retrier,
    RetryPolicy,
    Send,
    build_http_client,
    full_jitter,
    retry_after_s,
)
from planning.adapters.keys import TRANSPORT_LOGGER_NAME
from planning.errors import UpstreamBusy, UpstreamUnavailable
from planning.tests.adapters.support import FakeTime, ceiling, make_retrier

BASE_URL = "https://vendor.example.com"


def _sender(responses: list[httpx.Response | Exception]) -> tuple[list[int], Send]:
    calls: list[int] = []

    async def send() -> httpx.Response:
        calls.append(1)
        outcome = responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return calls, send


async def test_limiter_spaces_call_starts() -> None:
    fake_time = FakeTime()
    limiter = RateLimiter(max_calls_per_s=5, clock=fake_time.clock, sleep=fake_time.sleep)

    for _ in range(3):
        await limiter.acquire()

    assert fake_time.sleeps == pytest.approx([0.2, 0.2])
    assert fake_time.now_s == pytest.approx(0.4)


async def test_limiter_does_not_wait_after_a_quiet_period() -> None:
    fake_time = FakeTime()
    limiter = RateLimiter(max_calls_per_s=5, clock=fake_time.clock, sleep=fake_time.sleep)
    await limiter.acquire()
    fake_time.now_s = 10.0

    await limiter.acquire()

    assert fake_time.sleeps == []


async def test_retry_on_503_then_success() -> None:
    fake_time = FakeTime()
    calls, send = _sender([httpx.Response(503), httpx.Response(200)])

    response = await make_retrier(fake_time).send("op", send)

    assert response.status_code == 200
    assert len(calls) == 2
    assert fake_time.sleeps == [0.5]


async def test_retry_after_is_honored_on_429() -> None:
    fake_time = FakeTime()
    _, send = _sender([httpx.Response(429, headers={"Retry-After": "2"}), httpx.Response(200)])

    response = await make_retrier(fake_time).send("op", send)

    assert response.status_code == 200
    assert fake_time.sleeps == [2.0]


async def test_backoff_grows_and_429_ends_busy() -> None:
    fake_time = FakeTime()
    calls, send = _sender([httpx.Response(429), httpx.Response(429), httpx.Response(429)])

    with pytest.raises(UpstreamBusy):
        await make_retrier(fake_time).send("op", send)

    assert len(calls) == 3
    assert fake_time.sleeps == [0.5, 1.0]


async def test_backoff_is_capped() -> None:
    retrier = Retrier(
        provider="test",
        policy=RetryPolicy(attempts=10, base_delay_s=1.0, max_delay_s=3.0),
        jitter=ceiling,
    )

    assert [retrier.backoff_s(attempt) for attempt in (1, 2, 3, 4)] == [1.0, 2.0, 3.0, 3.0]


async def test_retry_after_longer_than_the_cap_gives_up_at_once() -> None:
    fake_time = FakeTime()
    calls, send = _sender([httpx.Response(429, headers={"Retry-After": "3600"})])

    with pytest.raises(UpstreamBusy):
        await make_retrier(fake_time).send("op", send)

    assert len(calls) == 1
    assert fake_time.sleeps == []


async def test_timeouts_end_unavailable() -> None:
    fake_time = FakeTime()
    calls, send = _sender([httpx.ReadTimeout("slow")] * 3)

    with pytest.raises(UpstreamUnavailable):
        await make_retrier(fake_time).send("op", send)

    assert len(calls) == 3


async def test_5xx_after_last_attempt_is_unavailable() -> None:
    fake_time = FakeTime()
    calls, send = _sender([httpx.Response(502)] * 3)

    with pytest.raises(UpstreamUnavailable):
        await make_retrier(fake_time).send("op", send)

    assert len(calls) == 3


async def test_other_4xx_is_returned_without_retry() -> None:
    fake_time = FakeTime()
    calls, send = _sender([httpx.Response(400)])

    response = await make_retrier(fake_time).send("op", send)

    assert response.status_code == 400
    assert len(calls) == 1


async def test_retrier_uses_the_limiter_before_every_attempt() -> None:
    fake_time = FakeTime()
    limiter = RateLimiter(max_calls_per_s=5, clock=fake_time.clock, sleep=fake_time.sleep)
    _, send = _sender([httpx.Response(503), httpx.Response(200)])

    await make_retrier(fake_time, limiter).send("op", send)

    assert fake_time.sleeps == [0.5]


def test_retry_after_accepts_an_http_date() -> None:
    now = datetime(2026, 11, 17, 6, 0, 0, tzinfo=UTC)
    response = httpx.Response(429, headers={"Retry-After": "Tue, 17 Nov 2026 06:00:07 GMT"})

    assert retry_after_s(response, now) == 7.0


def test_retry_after_ignores_garbage() -> None:
    now = datetime(2026, 11, 17, 6, 0, 0, tzinfo=UTC)

    assert retry_after_s(httpx.Response(429, headers={"Retry-After": "soon"}), now) is None
    assert retry_after_s(httpx.Response(429), now) is None


def test_full_jitter_stays_under_the_ceiling() -> None:
    assert all(0 <= full_jitter(2.0) <= 2.0 for _ in range(100))


async def test_client_has_timeouts_and_quiet_transport_logs() -> None:
    logging.getLogger(TRANSPORT_LOGGER_NAME).setLevel(logging.NOTSET)

    async with build_http_client(BASE_URL, 5.0, 30.0) as client:
        assert client.timeout.connect == 5.0
        assert client.timeout.read == 30.0
        assert client.timeout.pool == 30.0

    assert logging.getLogger(TRANSPORT_LOGGER_NAME).level == logging.WARNING
