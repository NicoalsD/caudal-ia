"""Smoke test with the real Chronos weights; it downloads the model.

Skipped by default. Run it with ``uv run pytest -m chronos``.
"""

import math
from datetime import date

import pytest

from caudal_ia.config import get_settings
from caudal_ia.forecasting.creator import ChronosForecasterCreator
from caudal_ia.forecasting.pipeline import ForecastInput, ServingForecastPipeline
from caudal_ia.model_catalog import CHRONOS_MODEL_SPECS

pytestmark = pytest.mark.chronos

PREDICTION_LENGTH = 3
VALUES = [3.10, 3.02, 2.90, math.nan, 2.60, 2.35, 2.10, 2.00]


@pytest.mark.parametrize("spec", CHRONOS_MODEL_SPECS, ids=lambda spec: spec.name)
def test_real_model_returns_ordered_daily_quantiles(spec: object) -> None:
    settings = get_settings()
    forecaster = ChronosForecasterCreator().create(spec, settings)  # type: ignore[arg-type]
    pipeline = ServingForecastPipeline(lambda: forecaster, settings)
    timestamps = [f"2026-10-{day:02d}T18:00:00-05:00" for day in range(1, 9)]
    readings = [value for value in VALUES if math.isfinite(value)]
    days = [
        ts for ts, value in zip(timestamps, VALUES, strict=True) if math.isfinite(value)
    ]

    result = pipeline.run(
        ForecastInput(days, readings, PREDICTION_LENGTH, [0.1, 0.5, 0.9])
    )

    assert len(result.points) == PREDICTION_LENGTH
    assert result.points[0].timestamp.date() == date(2026, 10, 9)
    assert result.notes is not None
    assert all(point.p10 <= point.p50 <= point.p90 for point in result.points)
