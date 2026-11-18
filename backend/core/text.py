"""Messages of the project package: startup errors and API metadata."""

API_TITLE = "Weather routes API"

ADMIN_URL_IS_DEFAULT = "ADMIN_URL must not be the default 'admin/'; choose a non-default path"


def provider_secret_missing(variable: str, provider: str) -> str:
    """Message for a chosen provider whose secret is not set."""
    return f"{variable} is required because the provider '{provider}' is chosen"


def environment_invalid(problems: list[str]) -> str:
    """Message listing every invalid environment variable."""
    listed = "\n".join(f"  - {problem}" for problem in problems)
    return f"Invalid environment configuration:\n{listed}"
