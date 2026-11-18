"""Readiness: whether this process can serve requests: the database is reachable and a rule set
is active. Calls no third party."""

import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from asgiref.sync import sync_to_async
from django.db import DatabaseError, connection

from core.events import READINESS_CHECK_FAILED
from rulesets.services.active import has_active_rule_set

logger = logging.getLogger(__name__)


class ReadinessCheck(StrEnum):
    """The checks readiness runs."""

    DATABASE = "database"
    RULE_SET = "rule_set"


class CheckStatus(StrEnum):
    """The outcome of one check."""

    OK = "ok"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    """The outcome of every check."""

    checks: Mapping[ReadinessCheck, CheckStatus]

    @property
    def is_ready(self) -> bool:
        """True when every check passed."""
        return all(status is CheckStatus.OK for status in self.checks.values())


def _connect_to_database() -> None:
    connection.ensure_connection()


async def _check_database() -> bool:
    try:
        await sync_to_async(_connect_to_database)()
    except DatabaseError:
        return False
    return True


async def _check_rule_set() -> bool:
    try:
        return await has_active_rule_set()
    except DatabaseError:
        return False


CHECKS: Mapping[ReadinessCheck, Callable[[], Awaitable[bool]]] = MappingProxyType(
    {ReadinessCheck.DATABASE: _check_database, ReadinessCheck.RULE_SET: _check_rule_set},
)


async def check_readiness(
    checks: Mapping[ReadinessCheck, Callable[[], Awaitable[bool]]] = CHECKS,
) -> ReadinessReport:
    """Run the readiness checks and report each outcome."""
    results: dict[ReadinessCheck, CheckStatus] = {}
    for check, run in checks.items():
        passed = await run()
        results[check] = CheckStatus.OK if passed else CheckStatus.FAILED
        if not passed:
            logger.warning(READINESS_CHECK_FAILED, extra={"check": check.value})
    return ReadinessReport(checks=MappingProxyType(results))
