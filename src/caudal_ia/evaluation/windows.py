from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

from caudal_ia.forecasting.preprocessing import DailySeries

MINIMUM_PARAMETER = 1


@dataclass(frozen=True)
class BacktestWindow:
    """One cutoff of the backtest: the context known up to it and the days ahead."""

    cutoff_day: date
    context: tuple[float, ...]
    target_days: tuple[date, ...]
    targets: tuple[float, ...]


@dataclass(frozen=True)
class BacktestParameters:
    """How the rolling windows are cut from a daily series.

    ``min_context`` counts days, not valid readings: the first window has
    ``min_context`` days of context.
    """

    horizon: int
    min_context: int
    step: int

    def __post_init__(self) -> None:
        for name, value in (
            ("horizon", self.horizon),
            ("min_context", self.min_context),
            ("step", self.step),
        ):
            if value < MINIMUM_PARAMETER:
                raise ValueError(f"{name} must be at least {MINIMUM_PARAMETER}.")


class RollingWindowIterator(Iterator[BacktestWindow]):
    """Walk a daily series and emit one window per cutoff.

    Window ``k`` uses every day up to its cutoff as context (expanding window)
    and the ``horizon`` days after it as targets. Only windows whose horizon
    fits inside the series are emitted. Targets may be NaN for days without
    readings; the metrics ignore them.

    @pattern P14 Iterator
    """

    def __init__(self, series: DailySeries, parameters: BacktestParameters) -> None:
        self._series = series
        self._parameters = parameters
        self._cutoff_index = parameters.min_context - 1

    def __iter__(self) -> "RollingWindowIterator":
        return self

    def __next__(self) -> BacktestWindow:
        cutoff = self._cutoff_index
        last_target = cutoff + self._parameters.horizon
        if last_target >= len(self._series.days):
            raise StopIteration
        self._cutoff_index += self._parameters.step
        first_target = cutoff + 1
        return BacktestWindow(
            cutoff_day=self._series.days[cutoff],
            context=self._series.values[: cutoff + 1],
            target_days=self._series.days[first_target : last_target + 1],
            targets=self._series.values[first_target : last_target + 1],
        )
