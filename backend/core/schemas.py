"""Response schemas of the operational endpoints and the error envelope of every endpoint."""

from enum import StrEnum

from ninja import Schema

from core.readiness import CheckStatus, ReadinessCheck
from planning.errors import ErrorCode


class ErrorDetailOut(Schema):
    """One field-level problem. `field` is a dotted path to the request field."""

    field: str
    message: str


class ErrorBodyOut(Schema):
    """A catalog error: its code, a message for the driver, and field details if any."""

    code: ErrorCode
    message: str
    details: list[ErrorDetailOut] | None


class ErrorOut(Schema):
    """The body of every error response."""

    error: ErrorBodyOut


class HealthStatus(StrEnum):
    """The only answer a live process gives."""

    OK = "ok"


class HealthOut(Schema):
    """The process is up."""

    status: HealthStatus


class ReadinessOut(Schema):
    """Whether the process can serve requests, and the outcome of each check."""

    ready: bool
    checks: dict[ReadinessCheck, CheckStatus]
