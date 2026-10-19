import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

import pandas as pd


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
) -> DailySeries:
    """Group readings by local calendar day, keeping the last value of each day."""
    local = to_local_series(timestamps, values, timezone)
    local_index = pd.DatetimeIndex(local.index)
    daily = local.groupby(local_index.date).last()
    return DailySeries(
        days=tuple(daily.index),
        values=tuple(float(value) for value in daily.to_numpy()),
    )
