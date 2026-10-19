import math
from collections.abc import Iterator
from datetime import date, timedelta

import pytest

from caudal_ia.evaluation.windows import (
    BacktestParameters,
    BacktestWindow,
    RollingWindowIterator,
)
from caudal_ia.forecasting.preprocessing import DailySeries

FIRST_DAY = date(2026, 10, 1)
VALUES = (1.0, 2.0, math.nan, 4.0, 5.0, 6.0)
SIX_DAYS = len(VALUES)
HORIZON = 2
MIN_CONTEXT = 2
THREE_WINDOWS = 3
TWO_WINDOWS = 2


def daily_series(values: tuple[float, ...] = VALUES) -> DailySeries:
    days = tuple(FIRST_DAY + timedelta(days=offset) for offset in range(len(values)))
    return DailySeries(days=days, values=values)


def windows(step: int = 1) -> list[BacktestWindow]:
    parameters = BacktestParameters(HORIZON, MIN_CONTEXT, step)
    return list(RollingWindowIterator(daily_series(), parameters))


def test_iterator_is_a_class_that_returns_itself() -> None:
    iterator = RollingWindowIterator(
        daily_series(), BacktestParameters(HORIZON, MIN_CONTEXT, 1)
    )

    assert isinstance(iterator, Iterator)
    assert iter(iterator) is iterator


def test_expanding_context_and_next_days_as_targets() -> None:
    emitted = windows()

    assert len(emitted) == THREE_WINDOWS
    first = emitted[0]
    assert first.cutoff_day == date(2026, 10, 2)
    assert first.context == VALUES[:2]
    assert first.target_days == (date(2026, 10, 3), date(2026, 10, 4))
    assert math.isnan(first.targets[0])
    assert first.targets[1] == VALUES[3]
    second = emitted[1]
    assert second.context[:2] == VALUES[:2]
    assert math.isnan(second.context[2])
    assert second.targets == VALUES[3:5]
    assert len(emitted[2].context) == MIN_CONTEXT + 2


def test_only_windows_with_a_full_horizon_are_emitted() -> None:
    last = windows()[-1]

    assert last.target_days[-1] == FIRST_DAY + timedelta(days=SIX_DAYS - 1)


def test_step_skips_cutoffs() -> None:
    emitted = windows(step=2)

    assert len(emitted) == TWO_WINDOWS
    assert [window.cutoff_day for window in emitted] == [
        date(2026, 10, 2),
        date(2026, 10, 4),
    ]


def test_series_shorter_than_context_plus_horizon_gives_no_windows() -> None:
    short = daily_series((1.0, 2.0, 3.0))
    parameters = BacktestParameters(HORIZON, MIN_CONTEXT + 1, 1)

    assert list(RollingWindowIterator(short, parameters)) == []


@pytest.mark.parametrize(
    "horizon, min_context, step",
    [(0, 1, 1), (1, 0, 1), (1, 1, 0)],
    ids=["horizon", "min-context", "step"],
)
def test_parameters_must_be_positive(horizon: int, min_context: int, step: int) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        BacktestParameters(horizon, min_context, step)
