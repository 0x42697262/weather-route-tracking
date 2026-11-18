"""The risk level table. Code reads a level's properties from its row and never compares against
a particular level (`docs/extensibility.md`)."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class RiskLevel(StrEnum):
    """The five fixed risk levels."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    NO_TRAVEL = "no_travel"


@dataclass(frozen=True, slots=True)
class LevelInfo:
    """A level's properties.

    Attributes:
        score: order and weight in the average risk; higher is worse.
        ranked: the level has its own distance key in the route ranking.
        blocks_recommendation: a route with distance at this level cannot be recommended.
        text_key: key of the level's label in the frontend text catalog.
        color_key: name of the level's color token on the frontend.
    """

    score: int
    ranked: bool
    blocks_recommendation: bool
    text_key: str
    color_key: str


RISK_LEVELS: Mapping[RiskLevel, LevelInfo] = MappingProxyType(
    {
        RiskLevel.LOW: LevelInfo(
            0, ranked=False, blocks_recommendation=False, text_key="low", color_key="risk-low"
        ),
        RiskLevel.MODERATE: LevelInfo(
            1,
            ranked=False,
            blocks_recommendation=False,
            text_key="moderate",
            color_key="risk-moderate",
        ),
        RiskLevel.HIGH: LevelInfo(
            2, ranked=True, blocks_recommendation=False, text_key="high", color_key="risk-high"
        ),
        RiskLevel.SEVERE: LevelInfo(
            3,
            ranked=True,
            blocks_recommendation=False,
            text_key="severe",
            color_key="risk-severe",
        ),
        RiskLevel.NO_TRAVEL: LevelInfo(
            4,
            ranked=True,
            blocks_recommendation=True,
            text_key="no_travel",
            color_key="risk-no-travel",
        ),
    },
)

LEVELS_BY_SCORE: tuple[RiskLevel, ...] = tuple(
    sorted(RISK_LEVELS, key=lambda level: RISK_LEVELS[level].score)
)
LOWEST_LEVEL: RiskLevel = LEVELS_BY_SCORE[0]


def score(level: RiskLevel) -> int:
    """The level's score."""
    return RISK_LEVELS[level].score


def worse(first: RiskLevel, second: RiskLevel) -> RiskLevel:
    """The worse (higher score) of two levels."""
    return first if score(first) >= score(second) else second


def worst(levels: Iterable[RiskLevel]) -> RiskLevel:
    """The worst of the levels; the lowest level when there are none."""
    result = LOWEST_LEVEL
    for level in levels:
        result = worse(result, level)
    return result
