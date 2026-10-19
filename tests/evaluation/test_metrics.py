import math
from datetime import date, timedelta

import pytest

from caudal_ia.evaluation.backtest import BacktestResult, WindowForecast
from caudal_ia.evaluation.metrics import HorizonMetrics, horizon_metrics
from caudal_ia.evaluation.windows import BacktestParameters, BacktestWindow

NAN = math.nan
FIRST_DAY = date(2026, 10, 1)
HORIZON = 2
PARAMETERS = BacktestParameters(horizon=HORIZON, min_context=1, step=1)
NO_FORECAST = (0.0, 0.0, 0.0)
EXPECTED_WQL_H1 = 2 / 33
EXPECTED_WQL_H2 = 0.032
EXPECTED_MAE_H1 = 1.5
EXPECTED_MAE_H2 = 1.5
EXPECTED_EVALUATED = 2


def window(
    index: int,
    targets: tuple[float, ...],
    quantiles: tuple[tuple[float, float, float], ...],
) -> WindowForecast:
    days = tuple(FIRST_DAY + timedelta(days=index + step) for step in range(HORIZON))
    return WindowForecast(
        BacktestWindow(
            cutoff_day=FIRST_DAY + timedelta(days=index),
            context=(1.0,),
            target_days=days,
            targets=targets,
        ),
        quantiles,
    )


def sample_result() -> BacktestResult:
    """Three windows; the second and third miss one target each (NaN)."""
    return BacktestResult(
        PARAMETERS,
        (
            window(
                0,
                (10.0, 20.0),
                ((9.0, 11.0, 13.0), (18.0, 19.0, 21.0)),
            ),
            window(1, (12.0, NAN), ((11.0, 10.0, 12.0), NO_FORECAST)),
            window(2, (NAN, 30.0), (NO_FORECAST, (25.0, 28.0, 31.0))),
        ),
    )


def by_horizon(result: BacktestResult) -> dict[int, HorizonMetrics]:
    return {metrics.horizon: metrics for metrics in horizon_metrics(result)}


def test_mae_and_wql_by_hand_for_horizon_one() -> None:
    metrics = by_horizon(sample_result())[1]

    assert metrics.evaluated == EXPECTED_EVALUATED
    assert metrics.mae == pytest.approx(EXPECTED_MAE_H1)
    assert metrics.wql == pytest.approx(EXPECTED_WQL_H1)


def test_mae_and_wql_by_hand_for_horizon_two() -> None:
    metrics = by_horizon(sample_result())[2]

    assert metrics.evaluated == EXPECTED_EVALUATED
    assert metrics.mae == pytest.approx(EXPECTED_MAE_H2)
    assert metrics.wql == pytest.approx(EXPECTED_WQL_H2)


def test_nan_targets_are_ignored() -> None:
    metrics = by_horizon(sample_result())

    assert metrics[1].evaluated == EXPECTED_EVALUATED
    assert metrics[2].evaluated == EXPECTED_EVALUATED


def test_wql_is_none_when_the_absolute_targets_sum_to_zero() -> None:
    zero_result = BacktestResult(
        PARAMETERS,
        (window(0, (0.0, 0.0), ((1.0, 2.0, 3.0), (1.0, 2.0, 3.0))),),
    )

    metrics = by_horizon(zero_result)

    assert metrics[1].wql is None
    assert metrics[1].mae == pytest.approx(2.0)


def test_horizon_without_finite_targets_has_no_metrics() -> None:
    empty = BacktestResult(
        PARAMETERS,
        (window(0, (NAN, 1.0), (NO_FORECAST, (0.0, 1.0, 2.0))),),
    )

    metrics = by_horizon(empty)

    assert metrics[1] == HorizonMetrics(1, 0, None, None)
    assert metrics[2].evaluated == 1
