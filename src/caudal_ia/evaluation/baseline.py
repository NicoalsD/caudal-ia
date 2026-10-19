import math
from collections.abc import Sequence

import numpy as np

from caudal_ia.forecasting.forecaster import Forecaster, QuantileForecast
from caudal_ia.forecasting.quantiles import P50_LEVEL

PERSISTENCE_NAME = "naive-persistence"
PERSISTENCE_VERSION = "1"
DEFAULT_MINIMUM_CHANGES = 5


class PersistenceForecaster(Forecaster):
    """Estimate that the level stays where it was, with the band of past changes.

    ``L`` is the last finite value of the context and ``d_t`` the daily changes
    between consecutive finite values. The median is ``L``; every other level is
    ``L`` plus the same quantile of the changes, for every step. The lower level
    is capped at ``L`` and the upper one floored at ``L``, so the band always
    contains the median: on a steady rise, ``L + Q(0.1)`` would otherwise sit
    above ``L``. With fewer than ``min_changes`` valid changes, every level is
    ``L`` (no invented range).

    @pattern P19 Strategy
    """

    def __init__(self, min_changes: int = DEFAULT_MINIMUM_CHANGES) -> None:
        self._min_changes = min_changes

    @property
    def name(self) -> str:
        return PERSISTENCE_NAME

    @property
    def version(self) -> str:
        return PERSISTENCE_VERSION

    def predict_quantiles(
        self,
        context: Sequence[float],
        prediction_length: int,
        quantile_levels: Sequence[float],
    ) -> QuantileForecast:
        last = last_finite(context)
        changes = daily_changes(context)
        levels = tuple(quantile_levels)
        if len(changes) < self._min_changes:
            values = {level: last for level in levels}
        else:
            values = {level: band_value(last, changes, level) for level in levels}
        steps = tuple(
            tuple(values[level] for level in levels) for _ in range(prediction_length)
        )
        return QuantileForecast(levels, steps)


def last_finite(context: Sequence[float]) -> float:
    for value in reversed(context):
        if math.isfinite(value):
            return float(value)
    raise ValueError("The context has no finite value.")


def daily_changes(context: Sequence[float]) -> list[float]:
    """Changes between consecutive days that both have a finite value."""
    return [
        float(current - previous)
        for previous, current in zip(context, context[1:], strict=False)
        if math.isfinite(previous) and math.isfinite(current)
    ]


def band_value(last: float, changes: list[float], level: float) -> float:
    if level == P50_LEVEL:
        return last
    shifted = last + float(np.quantile(np.asarray(changes), level))
    if level < P50_LEVEL:
        return min(last, shifted)
    return max(last, shifted)


def skill(model_mae: float | None, persistence_mae: float | None) -> float | None:
    """Relative improvement over persistence: ``1 - MAE_model / MAE_persistence``.

    ``None`` when either MAE is missing or the persistence MAE is zero.
    """
    if model_mae is None or persistence_mae is None or persistence_mae == 0:
        return None
    return 1.0 - model_mae / persistence_mae
