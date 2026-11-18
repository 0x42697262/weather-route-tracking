"""Sum a route's stretches into distances per level, Unknown and ferry distance, the average risk
and warnings (`docs/risk-model.md`)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from planning.domain.risk_constants import RANKING_DISTANCE_DECIMALS
from planning.domain.stretches import Stretch, StretchKind
from shared.risk_levels import LEVELS_BY_SCORE, RISK_LEVELS, RiskLevel


class RouteWarning(StrEnum):
    """Warnings a route summary can carry."""

    UNKNOWN_WEATHER = "unknown_weather"
    FERRY_CROSSING = "ferry_crossing"
    HAS_BLOCKING_LEVEL = "has_blocking_level"


@dataclass(frozen=True, slots=True)
class StretchKindInfo:
    """A stretch kind's properties.

    Attributes:
        warning: the warning a route with a stretch of this kind carries, if any.
    """

    warning: RouteWarning | None


STRETCH_KINDS: Mapping[StretchKind, StretchKindInfo] = MappingProxyType(
    {
        StretchKind.RATED: StretchKindInfo(warning=None),
        StretchKind.UNKNOWN: StretchKindInfo(warning=RouteWarning.UNKNOWN_WEATHER),
        StretchKind.FERRY: StretchKindInfo(warning=RouteWarning.FERRY_CROSSING),
    },
)


@dataclass(frozen=True, slots=True)
class RouteSummary:
    """A route's distances and risk, all in km.

    Attributes:
        distance_km_by_level: every level, 0 when the route has none of it. Rated stretches and
            ferry stretches with a ferry level count here.
        unknown_km: distance with no forecast.
        ferry_km: distance on ferry stretches that are not rated.
        total_km: the sum of all stretches; equals the per-level sum plus Unknown plus ferry.
        weather_rated_km: distance rated from a forecast (rated stretches only; a ferry with a
            ferry level is not weather).
        worst_level: the highest-score level with distance (rounded to
            `RANKING_DISTANCE_DECIMALS`) above 0; None when no stretch has a level.
        blocking_km: distance at levels that block a recommendation.
        average_risk: level score times km over km, across stretches with a level; None when no
            stretch has one.
        blocked: distance at a level that blocks a recommendation, rounded to
            `RANKING_DISTANCE_DECIMALS`, is above 0.
        warnings: in `RouteWarning` order, each at most once.
    """

    distance_km_by_level: Mapping[RiskLevel, float]
    unknown_km: float
    ferry_km: float
    total_km: float
    weather_rated_km: float
    worst_level: RiskLevel | None
    blocking_km: float
    average_risk: float | None
    blocked: bool
    warnings: tuple[RouteWarning, ...]

    @property
    def known_km(self) -> float:
        """Distance with a level."""
        return sum(self.distance_km_by_level.values())


def _distance_by_level(stretches: Sequence[Stretch]) -> dict[RiskLevel, float]:
    distances = dict.fromkeys(LEVELS_BY_SCORE, 0.0)
    for stretch in stretches:
        if stretch.level is not None:
            distances[stretch.level] += stretch.length_km
    return distances


def _unrated_km_by_kind(stretches: Sequence[Stretch]) -> dict[StretchKind, float]:
    distances = dict.fromkeys(StretchKind, 0.0)
    for stretch in stretches:
        if stretch.level is None:
            distances[stretch.kind] += stretch.length_km
    return distances


def _average_risk(distances: Mapping[RiskLevel, float]) -> float | None:
    known_km = sum(distances.values())
    if known_km <= 0:
        return None
    weighted = sum(RISK_LEVELS[level].score * km for level, km in distances.items())
    return weighted / known_km


def _worst_level(distances: Mapping[RiskLevel, float]) -> RiskLevel | None:
    reached = [
        level for level in LEVELS_BY_SCORE if round(distances[level], RANKING_DISTANCE_DECIMALS) > 0
    ]
    return reached[-1] if reached else None


def _blocking_km(distances: Mapping[RiskLevel, float]) -> float:
    return sum(km for level, km in distances.items() if RISK_LEVELS[level].blocks_recommendation)


def _blocked(distances: Mapping[RiskLevel, float]) -> bool:
    return any(
        RISK_LEVELS[level].blocks_recommendation and round(km, RANKING_DISTANCE_DECIMALS) > 0
        for level, km in distances.items()
    )


def _warnings(stretches: Sequence[Stretch], *, blocked: bool) -> tuple[RouteWarning, ...]:
    present = {
        STRETCH_KINDS[stretch.kind].warning for stretch in stretches if stretch.length_km > 0
    }
    if blocked:
        present.add(RouteWarning.HAS_BLOCKING_LEVEL)
    return tuple(warning for warning in RouteWarning if warning in present)


def summarize(stretches: Sequence[Stretch]) -> RouteSummary:
    """Summarize one route's stretches."""
    distances = _distance_by_level(stretches)
    unrated = _unrated_km_by_kind(stretches)
    blocked = _blocked(distances)
    return RouteSummary(
        distance_km_by_level=MappingProxyType(distances),
        unknown_km=unrated[StretchKind.UNKNOWN],
        ferry_km=unrated[StretchKind.FERRY],
        total_km=sum(stretch.length_km for stretch in stretches),
        weather_rated_km=sum(
            stretch.length_km for stretch in stretches if stretch.kind is StretchKind.RATED
        ),
        worst_level=_worst_level(distances),
        blocking_km=_blocking_km(distances),
        average_risk=_average_risk(distances),
        blocked=blocked,
        warnings=_warnings(stretches, blocked=blocked),
    )
