"""The request id of the request being served, and the log filter that stamps it on records."""

import logging
from contextvars import ContextVar

current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Adds `request_id` to every record logged while a request is served."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Stamp the record; never drops it."""
        request_id = current_request_id.get()
        if request_id is not None:
            record.request_id = request_id
        return True
