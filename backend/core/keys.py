"""URL prefixes, paths and patterns of the project package."""

API_PREFIX = "api/"
API_V1_PREFIX = "v1/"
API_DOCS_PATH = "docs"
HEALTH_PATH = "health"
READY_PATH = "ready"
API_URL_NAMESPACE = "api"

STATIC_URL_PATH = "/django-static/"
STATIC_ROOT_DIRNAME = "staticfiles"

DEFAULT_ADMIN_URL = "admin/"
ADMIN_URL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]*/$"
PUBLIC_HOST_PATTERN = (
    r"^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*$"
)

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = r"[A-Za-z0-9._-]{1,64}"
FORWARDED_FOR_HEADER = "X-Forwarded-For"
FORWARDED_FOR_SEPARATOR = ","
REMOTE_ADDR_META = "REMOTE_ADDR"
RATE_LIMIT_CACHE_PREFIX = "rate"


def v1_path(path: str) -> str:
    """The request path of a `/api/v1/` endpoint."""
    return f"/{API_PREFIX}{API_V1_PREFIX}{path}"


def rate_limit_cache_key(scope: str, client: str, window: int) -> str:
    """The cache key counting one client's requests in one scope and window."""
    return f"{RATE_LIMIT_CACHE_PREFIX}:{scope}:{client}:{window}"
