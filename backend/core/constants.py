"""Fixed internal constants of the project package."""

API_VERSION = "1"
WEB_BIND_HOST = "0.0.0.0"  # noqa: S104
WEB_PORT = 8000
WEB_APPLICATION = "core.asgi:application"

RATE_LIMIT_WINDOW_S = 60
PLACES_RATE_LIMIT_PER_MINUTE = 60
