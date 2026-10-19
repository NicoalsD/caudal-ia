import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

ONE_DAY = timedelta(days=1)


@dataclass(frozen=True)
class DailySeries:
    """One value per consecutive local day; NaN marks a day without readings."""

    days: tuple[date, ...]
    values: tuple[float, ...]

    @property
    def last_day(self) -> date:
        return self.days[-1]

    @property
    def valid_points(self) -> int:
        return sum(1 for value in self.values if math.isfinite(value))

    @property
    def missing_days(self) -> int:
        return len(self.values) - self.valid_points


def describe_gaps(series: DailySeries) -> str | None:
    """Explain the days without readings for ``model.notes``.

    Chronos-2 and Chronos-Bolt treat NaN in the context as missing values, so gaps
    are passed to the model as they are instead of being filled in.
    """
    if series.missing_days == 0:
        return None
    return (
        f"{series.missing_days} días sin lectura se enviaron al modelo como "
        "valores faltantes, sin rellenar."
    )


class DailyAggregation(ABC):
    """Reduce the readings of one local day to a single value.

    @pattern P19 Strategy
    """

    @abstractmethod
    def aggregate(self, readings_by_day: Any) -> "pd.Series[float]":
        """Return one value per day from a pandas ``SeriesGroupBy``."""


class LastValueAggregation(DailyAggregation):
    """Keep the last reading of the day, the closest to the next day."""

    def aggregate(self, readings_by_day: Any) -> "pd.Series[float]":
        result: pd.Series[float] = readings_by_day.last()
        return result


class MeanAggregation(DailyAggregation):
    """Average every reading of the day."""

    def aggregate(self, readings_by_day: Any) -> "pd.Series[float]":
        result: pd.Series[float] = readings_by_day.mean()
        return result


DAILY_AGGREGATIONS: dict[str, DailyAggregation] = {
    "last": LastValueAggregation(),
    "mean": MeanAggregation(),
}


def to_local_series(
    timestamps: Sequence[str],
    values: Sequence[float],
    timezone: ZoneInfo,
) -> "pd.Series[float]":
    """Parse ISO-8601 timestamps and express them in the aqueduct time zone.

    Readings are sorted by instant; when two share the same instant the last one
    received is kept.
    """
    instants = pd.to_datetime(list(timestamps), utc=True, format="ISO8601")
    series = pd.Series(list(values), index=pd.DatetimeIndex(instants), dtype="float64")
    series = series[~series.index.duplicated(keep="last")].sort_index()
    return series.tz_convert(timezone)


def prepare_daily_series(
    timestamps: Sequence[str],
    values: Sequence[float],
    timezone: ZoneInfo,
    aggregation: DailyAggregation,
) -> DailySeries:
    """Resample readings to one value per local day from the first to the last day.

    Days without readings stay as NaN.
    """
    local = to_local_series(timestamps, values, timezone)
    local_index = pd.DatetimeIndex(local.index)
    daily = aggregation.aggregate(local.groupby(local_index.date))
    first_day: date = daily.index[0]
    last_day: date = daily.index[-1]
    day_count = (last_day - first_day).days + 1
    days = tuple(first_day + offset * ONE_DAY for offset in range(day_count))
    resampled = daily.reindex(list(days))
    return DailySeries(
        days=days,
        values=tuple(float(value) for value in resampled.to_numpy()),
    )
