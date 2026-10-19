import logging
import time
from collections.abc import Sequence

from caudal_ia.forecasting.forecaster import Forecaster, QuantileForecast

logger = logging.getLogger(__name__)
MILLISECONDS_PER_SECOND = 1000


class ForecasterDecorator(Forecaster):
    """Wrap another forecaster and keep its name and version.

    @pattern P09 Decorator
    """

    def __init__(self, wrapped: Forecaster) -> None:
        self._wrapped = wrapped

    @property
    def name(self) -> str:
        return self._wrapped.name

    @property
    def version(self) -> str:
        return self._wrapped.version

    def predict_quantiles(
        self,
        context: Sequence[float],
        prediction_length: int,
        quantile_levels: Sequence[float],
    ) -> QuantileForecast:
        return self._wrapped.predict_quantiles(
            context, prediction_length, quantile_levels
        )


class TimingForecaster(ForecasterDecorator):
    """Log how long each inference takes, without any value of the series.

    @pattern P09 Decorator
    """

    def predict_quantiles(
        self,
        context: Sequence[float],
        prediction_length: int,
        quantile_levels: Sequence[float],
    ) -> QuantileForecast:
        started = time.perf_counter()
        try:
            return super().predict_quantiles(
                context, prediction_length, quantile_levels
            )
        finally:
            latency_ms = (time.perf_counter() - started) * MILLISECONDS_PER_SECOND
            logger.info(
                "Forecast inference model=%s context_points=%d "
                "prediction_length=%d latency_ms=%.1f",
                self.name,
                len(context),
                prediction_length,
                latency_ms,
            )
