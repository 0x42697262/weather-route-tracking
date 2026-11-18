"""Matching a distance against a list of allowed checkpoint spacings."""

import math
from collections.abc import Iterable

from rulesets.constants import SPACING_MATCH_RELATIVE_TOLERANCE
from rulesets.domain.schema import Spacing


def find_spacing(spacings: Iterable[Spacing], distance_km: float) -> Spacing | None:
    """The spacing whose km value equals `distance_km` within float noise, or None."""
    for spacing in spacings:
        if math.isclose(spacing.km, distance_km, rel_tol=SPACING_MATCH_RELATIVE_TOLERANCE):
            return spacing
    return None
