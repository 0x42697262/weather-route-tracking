"""The attribution a provider's data must be shown with."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Attribution:
    """A notice to show where the provider's data is displayed, with an optional link."""

    text: str
    url: str | None
