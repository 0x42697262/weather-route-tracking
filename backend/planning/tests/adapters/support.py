"""Helpers for adapter tests: recorded fixtures, a fake clock and a fake sleep."""

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from planning.adapters.http import RateLimiter, Retrier

FIXTURES = Path(__file__).parent / "fixtures"
TEST_API_KEY = "test-key-not-a-secret"


def fixture_text(name: str) -> str:
    """The raw text of a recorded response."""
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> object:
    """A recorded response, parsed."""
    payload: object = json.loads(fixture_text(name))
    return payload


@dataclass(slots=True)
class FakeTime:
    """A monotonic clock that only moves when `sleep` is awaited; records every sleep."""

    now_s: float = 0.0
    sleeps: list[float] = field(default_factory=list)

    def clock(self) -> float:
        """The current fake time."""
        return self.now_s

    async def sleep(self, delay_s: float) -> None:
        """Record the delay and advance the clock by it."""
        self.sleeps.append(delay_s)
        self.now_s += delay_s


def ceiling(value: float) -> float:
    """A jitter that always picks the ceiling, so delays are exact."""
    return value


def make_retrier(fake_time: FakeTime, limiter: RateLimiter | None = None) -> Retrier:
    """A retrier that never really sleeps and has no randomness."""
    return Retrier(provider="test", limiter=limiter, sleep=fake_time.sleep, jitter=ceiling)


class Recorder:
    """A mock transport handler answering from a queue and keeping every request."""

    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        outcome = self.responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
