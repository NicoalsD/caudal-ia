from collections.abc import Sequence
from typing import Any, Protocol

import torch

from caudal_ia.forecasting.forecaster import (
    Forecaster,
    ForecasterOutputError,
    QuantileForecast,
)

FIRST_SERIES = 0


class ChronosPipeline(Protocol):
    """Subset of the ``chronos-forecasting`` pipelines used by the adapter."""

    def predict_quantiles(
        self,
        inputs: list[torch.Tensor],
        prediction_length: int,
        quantile_levels: list[float],
    ) -> tuple[Any, Any]: ...


class ChronosForecasterAdapter(Forecaster):
    """Adapt a Chronos-2 or Chronos-Bolt pipeline to the ``Forecaster`` interface.

    Chronos-2 returns a list with one ``(variates, steps, quantiles)`` tensor per
    series, while Chronos-Bolt returns one ``(series, steps, quantiles)`` tensor.
    Both accept NaN in the context as missing values.

    @pattern P06 Adapter
    """

    def __init__(self, pipeline: ChronosPipeline, name: str, version: str) -> None:
        self._pipeline = pipeline
        self._name = name
        self._version = version

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
        levels = list(quantile_levels)
        inputs = [torch.tensor(list(context), dtype=torch.float32)]
        with torch.inference_mode():
            quantiles, _ = self._pipeline.predict_quantiles(
                inputs,
                prediction_length=prediction_length,
                quantile_levels=levels,
            )
        series_quantiles = torch.as_tensor(quantiles[FIRST_SERIES])
        expected_size = prediction_length * len(levels)
        if series_quantiles.numel() != expected_size:
            raise ForecasterOutputError(
                f"Chronos returned {series_quantiles.numel()} values; "
                f"expected {expected_size}."
            )
        steps = series_quantiles.reshape(prediction_length, len(levels)).tolist()
        return QuantileForecast(
            quantile_levels=tuple(levels),
            steps=tuple(tuple(float(value) for value in step) for step in steps),
        )
