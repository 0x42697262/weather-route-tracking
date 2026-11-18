import pytest

from shared.risk_levels import (
    LEVELS_BY_SCORE,
    LOWEST_LEVEL,
    RISK_LEVELS,
    RiskLevel,
    score,
    worse,
    worst,
)


def test_table_matches_risk_model() -> None:
    assert [
        (level, info.score, info.ranked, info.blocks_recommendation)
        for level, info in RISK_LEVELS.items()
    ] == [
        (RiskLevel.LOW, 0, False, False),
        (RiskLevel.MODERATE, 1, False, False),
        (RiskLevel.HIGH, 2, True, False),
        (RiskLevel.SEVERE, 3, True, False),
        (RiskLevel.NO_TRAVEL, 4, True, True),
    ]


def test_every_level_has_a_row_and_unique_score() -> None:
    assert set(RISK_LEVELS) == set(RiskLevel)
    assert len({info.score for info in RISK_LEVELS.values()}) == len(RiskLevel)


def test_levels_by_score_ascending_and_lowest_first() -> None:
    scores = [score(level) for level in LEVELS_BY_SCORE]

    assert scores == sorted(scores)
    assert LOWEST_LEVEL is LEVELS_BY_SCORE[0]


def test_blocking_levels_are_ranked() -> None:
    assert all(info.ranked for info in RISK_LEVELS.values() if info.blocks_recommendation)


@pytest.mark.parametrize("first", list(RiskLevel))
@pytest.mark.parametrize("second", list(RiskLevel))
def test_worse_is_the_higher_score(first: RiskLevel, second: RiskLevel) -> None:
    result = worse(first, second)

    assert score(result) == max(score(first), score(second))
    assert worse(second, first) is result


def test_worst() -> None:
    assert worst([]) is LOWEST_LEVEL
    assert worst(LEVELS_BY_SCORE) is LEVELS_BY_SCORE[-1]
    assert worst(reversed(LEVELS_BY_SCORE)) is LEVELS_BY_SCORE[-1]
