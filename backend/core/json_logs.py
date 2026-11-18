"""A log formatter that writes one JSON object per line."""

import json
import logging
from datetime import UTC, datetime

STANDARD_RECORD_FIELDS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()
    | {"message", "asctime", "color_message"},
)


class JsonFormatter(logging.Formatter):
    """Formats a record as JSON: time, level, logger, event, then any `extra` fields."""

    def format(self, record: logging.LogRecord) -> str:
        """Return the record as one JSON line."""
        entry: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        entry.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in STANDARD_RECORD_FIELDS
            },
        )
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)
