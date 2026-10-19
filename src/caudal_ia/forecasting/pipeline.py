from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from caudal_ia.config import Settings
from caudal_ia.domain import ForecastResult
from caudal_ia.forecasting.forecaster import Forecaster, QuantileForecast
from caudal_ia.forecasting.preprocessing import (
    DAILY_AGGREGATIONS,
    DailySeries,
    describe_gaps,
    prepare_daily_series,
    require_minimum_history,
)
from caudal_ia.forecasting.quantiles import to_forecast_points
from caudal_ia.forecasting.result_validation import validate_result

ONE_DAY = timedelta(days=1)
VERSION_SEPARATOR = "+"


@dataclass(frozen=True)
class ForecastInput:
    timestamps: Sequence[str]
    values: Sequence[float]
    prediction_length: int
    quantile_levels: Sequence[float]


def utc_now() -> datetime:
    return datetime.now(UTC)


class ForecastPipeline(ABC):
    """Run every forecast through the same preprocess, infer, postprocess steps.

    @pattern P20 Template Method
    """

    def run(self, request: ForecastInput) -> ForecastResult:
        series = self.preprocess(request)
        forecast = self.infer(series, request)
        return self.postprocess(series, forecast, request)

    @abstractmethod
    def preprocess(self, request: ForecastInput) -> DailySeries:
        """Turn the raw readings into the daily series sent to the model."""

    @abstractmethod
    def infer(self, series: DailySeries, request: ForecastInput) -> QuantileForecast:
        """Ask the model for the requested quantiles."""

    @abstractmethod
    def postprocess(
        self,
        series: DailySeries,
        forecast: QuantileForecast,
        request: ForecastInput,
    ) -> ForecastResult:
        """Build the result returned to the backend."""


class ServingForecastPipeline(ForecastPipeline):
    """Pipeline behind ``POST /v1/forecasts``: stateless, one series per call."""

    def __init__(
        self,
        forecaster: Forecaster,
        settings: Settings,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._forecaster = forecaster
        self._settings = settings
        self._clock = clock

    def model_version(self) -> str:
        """Model version plus the daily aggregation, which also changes results."""
        return (
            f"{self._forecaster.version}{VERSION_SEPARATOR}"
            f"{self._settings.resample_aggregation}"
        )

    def preprocess(self, request: ForecastInput) -> DailySeries:
        series = prepare_daily_series(
            request.timestamps,
            request.values,
            self._settings.zone,
            DAILY_AGGREGATIONS[self._settings.resample_aggregation],
        )
        require_minimum_history(series, self._settings.forecast_min_points)
        return series

    def infer(self, series: DailySeries, request: ForecastInput) -> QuantileForecast:
        return self._forecaster.predict_quantiles(
            series.values,
            request.prediction_length,
            request.quantile_levels,
        )

    def postprocess(
        self,
        series: DailySeries,
        forecast: QuantileForecast,
        request: ForecastInput,
    ) -> ForecastResult:
        first_day = series.last_day + ONE_DAY
        result = ForecastResult(
            model_name=self._forecaster.name,
            model_version=self.model_version(),
            generated_at=self._clock(),
            notes=describe_gaps(series),
            points=to_forecast_points(forecast, first_day, self._settings.zone),
        )
        validate_result(
            result, first_day, request.prediction_length, self._settings.zone
        )
        return result
