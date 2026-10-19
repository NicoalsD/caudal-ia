import math
from typing import Any

import pytest
import torch

from caudal_ia.forecasting.chronos_adapter import ChronosForecasterAdapter
from caudal_ia.forecasting.forecaster import ForecasterOutputError

LEVELS = [0.1, 0.5, 0.9]
PREDICTION_LENGTH = 2


def quantile_grid(prediction_length: int) -> torch.Tensor:
    return torch.tensor(
        [[step + level for level in LEVELS] for step in range(prediction_length)]
    )


class Chronos2LikePipeline:
    """Return a list with one (variates, steps, quantiles) tensor per series."""

    def __init__(self) -> None:
        self.inputs: list[torch.Tensor] = []

    def predict_quantiles(
        self,
        inputs: list[torch.Tensor],
        prediction_length: int,
        quantile_levels: list[float],
    ) -> tuple[Any, Any]:
        self.inputs = inputs
        return [quantile_grid(prediction_length).unsqueeze(0)], None


class BoltLikePipeline:
    """Return one (series, steps, quantiles) tensor for the whole batch."""

    def predict_quantiles(
        self,
        inputs: list[torch.Tensor],
        prediction_length: int,
        quantile_levels: list[float],
    ) -> tuple[Any, Any]:
        return quantile_grid(prediction_length).unsqueeze(0), None


class WrongShapePipeline:
    def predict_quantiles(
        self,
        inputs: list[torch.Tensor],
        prediction_length: int,
        quantile_levels: list[float],
    ) -> tuple[Any, Any]:
        return torch.zeros(1, prediction_length + 1, len(quantile_levels)), None


@pytest.mark.parametrize("pipeline", [Chronos2LikePipeline(), BoltLikePipeline()])
def test_both_chronos_output_shapes_become_steps_by_quantile(pipeline: Any) -> None:
    adapter = ChronosForecasterAdapter(pipeline, "model", "1")

    forecast = adapter.predict_quantiles([1.0, 2.0, 3.0], PREDICTION_LENGTH, LEVELS)

    assert forecast.quantile_levels == tuple(LEVELS)
    for step, quantiles in enumerate(forecast.steps):
        assert quantiles == pytest.approx([step + level for level in LEVELS])


def test_gaps_reach_the_model_as_nan() -> None:
    pipeline = Chronos2LikePipeline()
    adapter = ChronosForecasterAdapter(pipeline, "model", "1")

    adapter.predict_quantiles([1.0, math.nan, 3.0], PREDICTION_LENGTH, LEVELS)

    (context,) = pipeline.inputs
    assert context.dtype == torch.float32
    assert torch.isnan(context[1])


def test_unexpected_output_size_is_an_output_error() -> None:
    adapter = ChronosForecasterAdapter(WrongShapePipeline(), "model", "1")

    with pytest.raises(ForecasterOutputError):
        adapter.predict_quantiles([1.0, 2.0], PREDICTION_LENGTH, LEVELS)


def test_adapter_reports_name_and_version() -> None:
    adapter = ChronosForecasterAdapter(
        BoltLikePipeline(), "amazon/chronos-bolt-small", "2.3.2"
    )

    assert (adapter.name, adapter.version) == ("amazon/chronos-bolt-small", "2.3.2")
