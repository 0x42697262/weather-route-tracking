"""Where to add samples so a level change is located more closely (`docs/risk-model.md`, method
`refine`).

The service loops: `midpoints_to_sample`, then for each position an arrival time, a forecast and
`classify`, then `merge_samples`, until no midpoint is left or `REFINE_MAX_DEPTH` rounds ran.
Unknown counts as its own value: a stretch between an Unknown and a known sample is refined, so
the Unknown distance is located the same way as a change of level.
"""

import itertools
from collections.abc import Sequence

from planning.domain.risk_constants import HALF_STEP
from planning.domain.stretches import RouteSample


def midpoints_to_sample(samples: Sequence[RouteSample], min_length_km: float) -> tuple[float, ...]:
    """The midpoint of every pair of neighboring samples whose levels differ (Unknown included)
    and whose distance apart is greater than `min_length_km`, in route order."""
    return tuple(
        first.distance_km + (second.distance_km - first.distance_km) * HALF_STEP
        for first, second in itertools.pairwise(samples)
        if first.level != second.level and second.distance_km - first.distance_km > min_length_km
    )


def merge_samples(
    existing: Sequence[RouteSample], new: Sequence[RouteSample]
) -> tuple[RouteSample, ...]:
    """Both sets ordered by distance. A new sample at the distance of an existing one is dropped."""
    return tuple(
        sorted((*existing, *added_samples(existing, new)), key=lambda sample: sample.distance_km)
    )


def added_samples(
    existing: Sequence[RouteSample], new: Sequence[RouteSample]
) -> tuple[RouteSample, ...]:
    """The new samples whose distance no existing sample has; what `merge_samples` adds."""
    taken = {sample.distance_km for sample in existing}
    return tuple(sample for sample in new if sample.distance_km not in taken)
