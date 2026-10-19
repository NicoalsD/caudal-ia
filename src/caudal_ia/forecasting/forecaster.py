from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class QuantileForecast:
    """Quantile values per forecast step, in the order of ``quantile_levels``."""

    quantile_levels: tuple[float, ...]
    steps: tuple[tuple[float, ...], ...]


class ForecasterOutputError(Exception):
    """Raised when a model returns an output that does not match the request."""


class Forecaster(ABC):
    """Common interface of every forecasting strategy the service can run.

    The context may contain NaN for days without readings.

    @pattern P19 Strategy
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Model name reported in the response."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Model version reported in the response."""

    @abstractmethod
    def predict_quantiles(
        self,
        context: Sequence[float],
        prediction_length: int,
        quantile_levels: Sequence[float],
    ) -> QuantileForecast:
        """Forecast ``prediction_length`` steps after the context."""
