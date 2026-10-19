import math
from datetime import date
from zoneinfo import ZoneInfo

import pytest

from caudal_ia.forecasting.preprocessing import (
    DAILY_AGGREGATIONS,
    DailySeries,
    LastValueAggregation,
    MeanAggregation,
    describe_gaps,
    prepare_daily_series,
    require_minimum_history,
)
from caudal_ia.series_validation import InsufficientHistoryError

BOGOTA = ZoneInfo("America/Bogota")
FIRST_LEVEL = 2.0
LAST_LEVEL = 1.0
DAYS_WITH_READINGS = 2
EMPTY_DAYS = 2


def test_days_are_cut_at_local_midnight() -> None:
    # 04:00 UTC is still 23:00 of the previous day in Bogota.
    series = prepare_daily_series(
        ["2026-10-02T04:00:00Z", "2026-10-02T06:00:00Z"],
        [1.0, 2.0],
        BOGOTA,
        LastValueAggregation(),
    )

    assert series.days == (date(2026, 10, 1), date(2026, 10, 2))
    assert series.values == (1.0, 2.0)


def test_last_aggregation_keeps_the_latest_reading_of_the_day() -> None:
    series = prepare_daily_series(
        ["2026-10-01T18:00:00-05:00", "2026-10-01T06:00:00-05:00"],
        [2.0, 3.0],
        BOGOTA,
        LastValueAggregation(),
    )

    assert series.values == (2.0,)


def test_mean_aggregation_averages_the_day() -> None:
    series = prepare_daily_series(
        ["2026-10-01T06:00:00-05:00", "2026-10-01T18:00:00-05:00"],
        [2.0, 3.0],
        BOGOTA,
        MeanAggregation(),
    )

    assert series.values == (2.5,)


def test_missing_days_become_nan_between_first_and_last_day() -> None:
    series = prepare_daily_series(
        ["2026-10-01T18:00:00-05:00", "2026-10-04T18:00:00-05:00"],
        [2.0, 1.0],
        BOGOTA,
        LastValueAggregation(),
    )

    assert series.days == tuple(date(2026, 10, day) for day in range(1, 5))
    first, second, third, last = series.values
    assert first == FIRST_LEVEL
    assert math.isnan(second)
    assert math.isnan(third)
    assert last == LAST_LEVEL
    assert series.valid_points == DAYS_WITH_READINGS
    assert series.missing_days == EMPTY_DAYS


def test_aggregations_are_selected_by_setting_name() -> None:
    assert isinstance(DAILY_AGGREGATIONS["last"], LastValueAggregation)
    assert isinstance(DAILY_AGGREGATIONS["mean"], MeanAggregation)


def test_gaps_are_described_only_when_present() -> None:
    complete = DailySeries((date(2026, 10, 1),), (1.0,))
    with_gap = DailySeries(
        (date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)),
        (1.0, math.nan, 1.0),
    )

    assert describe_gaps(complete) is None
    note = describe_gaps(with_gap)
    assert note is not None
    assert note.endswith(": 1.")


def test_minimum_history_counts_valid_days_only() -> None:
    series = DailySeries(
        (date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)),
        (1.0, math.nan, 1.0),
    )

    require_minimum_history(series, 2)
    with pytest.raises(InsufficientHistoryError) as error:
        require_minimum_history(series, 3)

    assert (error.value.received, error.value.minimum) == (2, 3)
