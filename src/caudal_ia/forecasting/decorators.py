import hashlib
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Sequence

import numpy as np

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


class CachingForecaster(ForecasterDecorator):
    """Reuse the forecast of an identical request for a short time.

    The backend may ask twice for the same tank in a row (a scheduled run and a
    manual one). The key is a SHA-256 digest of the request, so the series values
    are never kept; only the forecast is, in memory, for at most ``ttl_seconds``
    and for at most ``max_entries`` requests.

    @pattern P09 Decorator
    """

    def __init__(
        self,
        wrapped: Forecaster,
        max_entries: int,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(wrapped)
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, QuantileForecast]] = OrderedDict()
        self._lock = threading.Lock()

    def predict_quantiles(
        self,
        context: Sequence[float],
        prediction_length: int,
        quantile_levels: Sequence[float],
    ) -> QuantileForecast:
        key = self._key(context, prediction_length, quantile_levels)
        cached = self._get(key)
        if cached is not None:
            return cached
        forecast = super().predict_quantiles(
            context, prediction_length, quantile_levels
        )
        self._put(key, forecast)
        return forecast

    def _key(
        self,
        context: Sequence[float],
        prediction_length: int,
        quantile_levels: Sequence[float],
    ) -> str:
        digest = hashlib.sha256()
        digest.update(np.asarray(context, dtype=np.float64).tobytes())
        digest.update(np.asarray(quantile_levels, dtype=np.float64).tobytes())
        digest.update(str(prediction_length).encode())
        return digest.hexdigest()

    def _get(self, key: str) -> QuantileForecast | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, forecast = entry
            if self._clock() >= expires_at:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return forecast

    def _put(self, key: str, forecast: QuantileForecast) -> None:
        with self._lock:
            self._entries[key] = (self._clock() + self._ttl_seconds, forecast)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
