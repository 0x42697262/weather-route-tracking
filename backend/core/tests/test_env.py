import pytest

from core.env import EnvironmentConfigError, load_env

VALID_ENVIRONMENT = {
    "DJANGO_SECRET_KEY": "x" * 50,
    "PUBLIC_HOST": "app.example.com",
    "ADMIN_URL": "staff-area/",
    "POSTGRES_DB": "routes",
    "POSTGRES_USER": "routes",
    "POSTGRES_PASSWORD": "password",
    "TOMTOM_API_KEY": "key",
}


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for variable in VALID_ENVIRONMENT:
        monkeypatch.delenv(variable, raising=False)
    for variable, value in VALID_ENVIRONMENT.items():
        monkeypatch.setenv(variable, value)
    return monkeypatch


def test_valid_environment_applies_defaults(environment: pytest.MonkeyPatch) -> None:
    app_env = load_env()

    assert app_env.django_debug is False
    assert app_env.behind_proxy is True
    assert app_env.postgres_host == "db"
    assert app_env.http_read_timeout_seconds == 30
    assert str(app_env.redis_url) == "redis://cache:6379/0"
    assert app_env.open_meteo_api_key is None


@pytest.mark.parametrize(
    "variable", ["DJANGO_SECRET_KEY", "PUBLIC_HOST", "ADMIN_URL", "POSTGRES_PASSWORD"]
)
def test_missing_required_variable_is_named(environment: pytest.MonkeyPatch, variable: str) -> None:
    environment.delenv(variable)

    with pytest.raises(EnvironmentConfigError, match=variable):
        load_env()


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("DJANGO_SECRET_KEY", "x" * 49),
        ("PUBLIC_HOST", "https://app.example.com"),
        ("PUBLIC_HOST", "app.example.com/path"),
        ("ADMIN_URL", "/staff/"),
        ("ADMIN_URL", "staff"),
        ("POSTGRES_PORT", "70000"),
        ("HTTP_READ_TIMEOUT_SECONDS", "0"),
        ("OUTBOUND_CONCURRENCY", "-1"),
        ("ROUTE_PROVIDER", "mapbox"),
        ("LOG_LEVEL", "LOUD"),
    ],
)
def test_invalid_value_is_named(environment: pytest.MonkeyPatch, variable: str, value: str) -> None:
    environment.setenv(variable, value)

    with pytest.raises(EnvironmentConfigError, match=variable):
        load_env()


def test_default_admin_url_is_rejected(environment: pytest.MonkeyPatch) -> None:
    environment.setenv("ADMIN_URL", "admin/")

    with pytest.raises(EnvironmentConfigError, match="ADMIN_URL"):
        load_env()


@pytest.mark.parametrize("value", ["", None])
def test_chosen_tomtom_needs_its_key(environment: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        environment.delenv("TOMTOM_API_KEY")
    else:
        environment.setenv("TOMTOM_API_KEY", value)

    with pytest.raises(EnvironmentConfigError, match="TOMTOM_API_KEY"):
        load_env()


def test_every_problem_is_reported_together(environment: pytest.MonkeyPatch) -> None:
    environment.delenv("DJANGO_SECRET_KEY")
    environment.delenv("POSTGRES_DB")

    with pytest.raises(EnvironmentConfigError) as raised:
        load_env()

    assert "DJANGO_SECRET_KEY" in str(raised.value)
    assert "POSTGRES_DB" in str(raised.value)


def test_secret_values_are_not_in_the_message(environment: pytest.MonkeyPatch) -> None:
    environment.setenv("DJANGO_SECRET_KEY", "short-secret-value")

    with pytest.raises(EnvironmentConfigError) as raised:
        load_env()

    assert "short-secret-value" not in str(raised.value)
