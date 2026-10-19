import math
from dataclasses import dataclass

from caudal_ia.evaluation.backtest import BacktestResult
from caudal_ia.forecasting.quantiles import P10_LEVEL, P50_LEVEL, P90_LEVEL

FIRST_HORIZON = 1
WQL_LEVELS = (P10_LEVEL, P50_LEVEL, P90_LEVEL)


@dataclass(frozen=True)
class HorizonMetrics:
    """Metrics of one horizon ``h`` (days ahead). Targets that are NaN are skipped.

    ``mae``, ``coverage`` and ``mean_width`` are ``None`` when there is nothing to
    evaluate; ``wql`` is also ``None`` when the sum of the absolute targets is zero.
    """

    horizon: int
    evaluated: int
    mae: float | None
    wql: float | None
    coverage: float | None
    mean_width: float | None


@dataclass(frozen=True)
class EvaluatedPoint:
    """One target with the quantiles forecast for it."""

    target: float
    p10: float
    p50: float
    p90: float


def evaluated_points(result: BacktestResult, horizon: int) -> list[EvaluatedPoint]:
    """Collect the finite targets of one horizon with their quantiles."""
    index = horizon - FIRST_HORIZON
    points: list[EvaluatedPoint] = []
    for forecast in result.windows:
        target = forecast.window.targets[index]
        if math.isfinite(target):
            p10, p50, p90 = forecast.quantiles[index]
            points.append(EvaluatedPoint(target, p10, p50, p90))
    return points


def pinball_loss(level: float, target: float, predicted: float) -> float:
    """Quantile loss QL_q(y, y_hat) for one quantile level ``q``."""
    if target >= predicted:
        return level * (target - predicted)
    return (1.0 - level) * (predicted - target)


def mean_absolute_error(points: list[EvaluatedPoint]) -> float | None:
    """MAE of the p50 over the points."""
    if not points:
        return None
    return sum(abs(point.target - point.p50) for point in points) / len(points)


def coverage(points: list[EvaluatedPoint]) -> float | None:
    """Fraction of targets inside ``[p10, p90]``; the bounds count as inside."""
    if not points:
        return None
    inside = sum(1 for point in points if point.p10 <= point.target <= point.p90)
    return inside / len(points)


def mean_width(points: list[EvaluatedPoint]) -> float | None:
    """Average width of the ``[p10, p90]`` band."""
    if not points:
        return None
    return sum(point.p90 - point.p10 for point in points) / len(points)


def weighted_quantile_loss(points: list[EvaluatedPoint]) -> float | None:
    """WQL over the levels 0.1, 0.5 and 0.9, normalized by the sum of |y|.

    ``WQL = (1/|Q|) * sum_q 2 * sum_t QL_q / sum_t |y_t|``. The result is ``None``
    when there are no points or when the sum of the absolute targets is zero.
    """
    if not points:
        return None
    scale = sum(abs(point.target) for point in points)
    if scale == 0:
        return None
    predictions = {
        P10_LEVEL: [point.p10 for point in points],
        P50_LEVEL: [point.p50 for point in points],
        P90_LEVEL: [point.p90 for point in points],
    }
    total = 0.0
    for level in WQL_LEVELS:
        loss = sum(
            pinball_loss(level, point.target, predicted)
            for point, predicted in zip(points, predictions[level], strict=True)
        )
        total += 2.0 * loss / scale
    return total / len(WQL_LEVELS)


def horizon_metrics(result: BacktestResult) -> tuple[HorizonMetrics, ...]:
    """Return the metrics of every horizon from 1 to the backtest horizon."""
    metrics: list[HorizonMetrics] = []
    for horizon in range(FIRST_HORIZON, result.parameters.horizon + 1):
        points = evaluated_points(result, horizon)
        metrics.append(
            HorizonMetrics(
                horizon=horizon,
                evaluated=len(points),
                mae=mean_absolute_error(points),
                wql=weighted_quantile_loss(points),
                coverage=coverage(points),
                mean_width=mean_width(points),
            )
        )
    return tuple(metrics)
