import math
from collections.abc import Sequence
from datetime import date, timedelta

import pytest

from caudal_ia.evaluation.backtest import (
    Backtest,
    BacktestResult,
    ModelBacktest,
    WindowForecast,
)
from caudal_ia.evaluation.windows import BacktestParameters, BacktestWindow
from caudal_ia.forecasting.forecaster import (
    Forecaster,
    ForecasterOutputError,
    QuantileForecast,
)
from caudal_ia.forecasting.preprocessing import DailySeries
from tests.fakes import DeterministicForecaster

FIRST_DAY = date(2026, 10, 1)
VALUES = (1.0, 2.0, math.nan, 4.0, 5.0, 6.0)
PARAMETERS = BacktestParameters(horizon=2, min_context=2, step=1)
WINDOW_COUNT = 3
LEVELS = (0.9, 0.5, 0.1)


def daily_series() -> DailySeries:
    days = tuple(FIRST_DAY + timedelta(days=offset) for offset in range(len(VALUES)))
    return DailySeries(days=days, values=VALUES)


class RecordingForecaster(Forecaster):
    """Remember what it was asked and answer with the context's last value."""

    def __init__(self) -> None:
        self.contexts: list[tuple[float, ...]] = []
        self.horizons: list[int] = []

    @property
    def name(self) -> str:
        return "recording"

    @property
    def version(self) -> str:
        return "1"

    def predict_quantiles(
        self,
        context: Sequence[float],
        prediction_length: int,
        quantile_levels: Sequence[float],
    ) -> QuantileForecast:
        self.contexts.append(tuple(context))
        self.horizons.append(prediction_length)
        return QuantileForecast(
            tuple(quantile_levels),
            tuple((1.0, 2.0, 3.0) for _ in range(prediction_length)),
        )


class CrossedForecaster(RecordingForecaster):
    """Return p10 above p90 and levels in a different order."""

    def predict_quantiles(
        self,
        context: Sequence[float],
        prediction_length: int,
        quantile_levels: Sequence[float],
    ) -> QuantileForecast:
        del context, quantile_levels
        return QuantileForecast(LEVELS, ((1.0, 2.0, 3.0),) * prediction_length)


class ShortForecaster(RecordingForecaster):
    """Return one step fewer than the horizon asked."""

    def predict_quantiles(
        self,
        context: Sequence[float],
        prediction_length: int,
        quantile_levels: Sequence[float],
    ) -> QuantileForecast:
        del context
        return QuantileForecast(
            tuple(quantile_levels), ((1.0, 2.0, 3.0),) * (prediction_length - 1)
        )


class RecordingBacktest(Backtest):
    """Check that ``run`` calls the abstract step once per window, in order."""

    def __init__(self, parameters: BacktestParameters) -> None:
        super().__init__(parameters)
        self.seen: list[date] = []

    def forecast_window(self, window: BacktestWindow) -> WindowForecast:
        self.seen.append(window.cutoff_day)
        return WindowForecast(window, ((0.0, 0.0, 0.0),) * len(window.targets))


def run_model(forecaster: Forecaster) -> BacktestResult:
    return ModelBacktest(PARAMETERS, forecaster).run(daily_series())


def test_run_forecasts_every_window_and_keeps_the_parameters() -> None:
    result = run_model(DeterministicForecaster())

    assert result.parameters == PARAMETERS
    assert len(result.windows) == WINDOW_COUNT
    for forecast in result.windows:
        assert len(forecast.quantiles) == PARAMETERS.horizon


def test_model_only_sees_the_context_of_each_window() -> None:
    forecaster = RecordingForecaster()

    run_model(forecaster)

    assert forecaster.contexts == [VALUES[:2], VALUES[:3], VALUES[:4]]
    assert set(forecaster.horizons) == {PARAMETERS.horizon}


def test_p50_repeats_the_last_finite_value_of_the_context() -> None:
    result = run_model(DeterministicForecaster())

    p50s = [forecast.quantiles[0][1] for forecast in result.windows]
    assert p50s == [VALUES[1], VALUES[1], VALUES[3]]


def test_crossed_quantiles_are_sorted_in_the_window_forecast() -> None:
    result = run_model(CrossedForecaster())

    assert result.windows[0].quantiles[0] == (1.0, 2.0, 3.0)


def test_wrong_number_of_steps_is_an_output_error() -> None:
    with pytest.raises(ForecasterOutputError):
        run_model(ShortForecaster())


def test_run_calls_the_abstract_step_once_per_window_and_summarizes() -> None:
    backtest = RecordingBacktest(PARAMETERS)

    result = backtest.run(daily_series())

    assert backtest.seen == [date(2026, 10, 2), date(2026, 10, 3), date(2026, 10, 4)]
    assert len(result.windows) == WINDOW_COUNT
