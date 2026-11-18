"""Names of the provider adapters an operator can choose in the environment.

`fake` is a deterministic, keyless set of providers for tests, the frontend end-to-end test and
offline demos (`planning/adapters/fake/`).
"""

from enum import StrEnum


class RouteProviderName(StrEnum):
    """Routing adapters that exist."""

    TOMTOM = "tomtom"
    FAKE = "fake"


class GeocoderName(StrEnum):
    """Place search adapters that exist."""

    TOMTOM = "tomtom"
    FAKE = "fake"


class WeatherProviderName(StrEnum):
    """Weather adapters that exist."""

    OPEN_METEO = "open_meteo"
    FAKE = "fake"
