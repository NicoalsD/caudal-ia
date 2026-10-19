import math
from collections.abc import Sequence

from caudal_ia.config import Settings
from caudal_ia.forecasting.creator import ForecasterCreator
from caudal_ia.forecasting.forecaster import Forecaster, QuantileForecast
from caudal_ia.model_catalog import ModelSpec

FAKE_SPREAD = 0.25
MEDIAN_LEVEL = 0.5


class DeterministicForecaster(Forecaster):
    """Repeat the last finite value and widen the range with each step."""

    def __init__(self, name: str = "fake/model", version: str = "test") -> None:
        self._name = name
        self._version = version
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    def predict_quantiles(
        self,
        context: Sequence[float],
        prediction_length: int,
        quantile_levels: Sequence[float],
    ) -> QuantileForecast:
        self.calls += 1
        last = next(value for value in reversed(context) if math.isfinite(value))
        steps = tuple(
            tuple(
                last + (level - MEDIAN_LEVEL) * FAKE_SPREAD * step
                for level in quantile_levels
            )
            for step in range(1, prediction_length + 1)
        )
        return QuantileForecast(tuple(quantile_levels), steps)


class FakeForecasterCreator(ForecasterCreator):
    """Build deterministic forecasters without loading any model weights."""

    def create_forecaster(self, spec: ModelSpec, settings: Settings) -> Forecaster:
        del settings
        return DeterministicForecaster(spec.name, spec.version)


class FailingForecasterCreator(ForecasterCreator):
    """Simulate a model whose weights cannot be loaded."""

    def create_forecaster(self, spec: ModelSpec, settings: Settings) -> Forecaster:
        raise OSError(f"cannot load {spec.name}")
