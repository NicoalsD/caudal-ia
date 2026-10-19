from abc import ABC, abstractmethod
from dataclasses import dataclass

from caudal_ia.evaluation.windows import (
    BacktestParameters,
    BacktestWindow,
    RollingWindowIterator,
)
from caudal_ia.forecasting.forecaster import Forecaster, ForecasterOutputError
from caudal_ia.forecasting.preprocessing import DailySeries
from caudal_ia.forecasting.quantiles import (
    CONTRACT_QUANTILE_LEVELS,
    ordered_contract_quantiles,
)


@dataclass(frozen=True)
class WindowForecast:
    """The window and its ``(p10, p50, p90)`` for each forecast step."""

    window: BacktestWindow
    quantiles: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class BacktestResult:
    """Every window forecast of one run, with the parameters that cut them."""

    parameters: BacktestParameters
    windows: tuple[WindowForecast, ...]


class Backtest(ABC):
    """Replay a daily series window by window and collect the forecasts.

    ``run`` fixes the order of the steps: iterate the windows, forecast each one
    with ``forecast_window`` (the step each subclass defines) and summarize the
    run. Metrics are computed from the result in ``metrics.py``.

    @pattern P20 Template Method
    """

    def __init__(self, parameters: BacktestParameters) -> None:
        self._parameters = parameters

    @property
    def parameters(self) -> BacktestParameters:
        return self._parameters

    def run(self, series: DailySeries) -> BacktestResult:
        forecasts = [
            self.forecast_window(window)
            for window in RollingWindowIterator(series, self._parameters)
        ]
        return self.summarize(forecasts)

    @abstractmethod
    def forecast_window(self, window: BacktestWindow) -> WindowForecast:
        """Forecast the targets of one window from its context only."""

    def summarize(self, forecasts: list[WindowForecast]) -> BacktestResult:
        return BacktestResult(self._parameters, tuple(forecasts))


class ModelBacktest(Backtest):
    """Backtest a ``Forecaster``, such as Chronos or the persistence baseline.

    The forecaster sees only the context of each window, never its targets.
    """

    def __init__(self, parameters: BacktestParameters, forecaster: Forecaster) -> None:
        super().__init__(parameters)
        self._forecaster = forecaster

    @property
    def forecaster(self) -> Forecaster:
        return self._forecaster

    def forecast_window(self, window: BacktestWindow) -> WindowForecast:
        horizon = len(window.targets)
        forecast = self._forecaster.predict_quantiles(
            window.context, horizon, CONTRACT_QUANTILE_LEVELS
        )
        quantiles = ordered_contract_quantiles(forecast)
        if len(quantiles) != horizon:
            raise ForecasterOutputError(
                f"Expected {horizon} steps, got {len(quantiles)}."
            )
        return WindowForecast(window, quantiles)
