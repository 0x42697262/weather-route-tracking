"""The environment schema: the only module that reads environment variables.

`load_env()` is called once, from `core.settings`. Everything else reads the resulting
`AppEnv` through `django.conf.settings.APP_ENV`.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, Self

from pydantic import (
    Field,
    HttpUrl,
    PositiveFloat,
    PositiveInt,
    RedisDsn,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.keys import ADMIN_URL_PATTERN, DEFAULT_ADMIN_URL, PUBLIC_HOST_PATTERN
from core.provider_names import GeocoderName, RouteProviderName, WeatherProviderName
from core.text import (
    ADMIN_URL_IS_DEFAULT,
    environment_invalid,
    provider_secret_missing,
)

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

DJANGO_SECRET_KEY_MIN_LENGTH = 50
PORT_MAX = 65535

VENDOR_SECRET_FIELDS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        RouteProviderName.TOMTOM.value: ("tomtom_api_key",),
        GeocoderName.TOMTOM.value: ("tomtom_api_key",),
        WeatherProviderName.OPEN_METEO.value: (),
        RouteProviderName.FAKE.value: (),
    },
)


class EnvironmentConfigError(Exception):
    """The environment is missing a required variable or holds an invalid value."""


class AppEnv(BaseSettings):
    """Every environment variable the backend reads, typed and validated."""

    model_config = SettingsConfigDict(frozen=True, extra="ignore", case_sensitive=False)

    django_secret_key: SecretStr = Field(min_length=DJANGO_SECRET_KEY_MIN_LENGTH)
    django_debug: bool = False
    public_host: str = Field(pattern=PUBLIC_HOST_PATTERN)
    admin_url: str = Field(pattern=ADMIN_URL_PATTERN)
    behind_proxy: bool = True
    log_level: LogLevel = "INFO"
    web_workers: PositiveInt = 2

    postgres_host: str = "db"
    postgres_port: int = Field(default=5432, ge=1, le=PORT_MAX)
    postgres_db: str = Field(min_length=1)
    postgres_user: str = Field(min_length=1)
    postgres_password: SecretStr = Field(min_length=1)
    postgres_connect_timeout_seconds: PositiveInt = 5
    redis_url: RedisDsn = RedisDsn("redis://cache:6379/0")

    route_provider: RouteProviderName = RouteProviderName.TOMTOM
    geocoder: GeocoderName = GeocoderName.TOMTOM
    weather_provider: WeatherProviderName = WeatherProviderName.OPEN_METEO
    tomtom_api_key: SecretStr | None = None
    tomtom_base_url: HttpUrl = HttpUrl("https://api.tomtom.com")
    open_meteo_base_url: HttpUrl = HttpUrl("https://api.open-meteo.com")
    open_meteo_api_key: SecretStr | None = None

    http_connect_timeout_seconds: PositiveFloat = 5
    http_read_timeout_seconds: PositiveFloat = 30
    outbound_concurrency: PositiveInt = 8

    trip_max_distance_km: PositiveFloat = 3000
    trip_max_checkpoints_per_route: PositiveInt = 200
    route_alternatives_requested: PositiveInt = 4
    route_max_extra_requests: PositiveInt = 4
    weather_max_cells_per_trip: PositiveInt = 300
    forecast_cache_ttl_seconds: PositiveInt = 1800
    rate_limit_trips_per_minute: PositiveInt = 10

    @field_validator("tomtom_api_key", "open_meteo_api_key", mode="before")
    @classmethod
    def _empty_secret_is_unset(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _admin_url_is_not_default(self) -> Self:
        if self.admin_url == DEFAULT_ADMIN_URL:
            raise ValueError(ADMIN_URL_IS_DEFAULT)
        return self

    @model_validator(mode="after")
    def _chosen_providers_have_secrets(self) -> Self:
        chosen = (self.route_provider, self.geocoder, self.weather_provider)
        for provider in chosen:
            for field_name in VENDOR_SECRET_FIELDS[provider.value]:
                if getattr(self, field_name) is None:
                    raise ValueError(provider_secret_missing(field_name.upper(), provider.value))
        return self


def _describe(error: ValidationError) -> list[str]:
    problems = []
    for detail in error.errors():
        variable = ".".join(str(part) for part in detail["loc"]).upper() or "ENVIRONMENT"
        problems.append(f"{variable}: {detail['msg']}")
    return problems


def load_env() -> AppEnv:
    """Read and validate the environment.

    Raises:
        EnvironmentConfigError: naming every missing or invalid variable.
    """
    try:
        return AppEnv()
    except ValidationError as error:
        raise EnvironmentConfigError(environment_invalid(_describe(error))) from None
