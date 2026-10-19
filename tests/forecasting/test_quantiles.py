import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from caudal_ia.domain import ForecastPoint, ForecastResult
from caudal_ia.forecasting.forecaster import ForecasterOutputError, QuantileForecast
from caudal_ia.forecasting.quantiles import to_forecast_points
from caudal_ia.forecasting.result_validation import validate_result

BOGOTA = ZoneInfo("America/Bogota")
FIRST_DAY = date(2026, 10, 10)
LEVELS = (0.1, 0.5, 0.9)


def test_points_start_at_local_midnight_of_consecutive_days() -> None:
    forecast = QuantileForecast(LEVELS, ((1.0, 2.0, 3.0), (1.5, 2.5, 3.5)))

    points = to_forecast_points(forecast, FIRST_DAY, BOGOTA)

    assert [point.timestamp.isoformat() for point in points] == [
        "2026-10-10T00:00:00-05:00",
        "2026-10-11T00:00:00-05:00",
    ]
    assert (points[1].p10, points[1].p50, points[1].p90) == (1.5, 2.5, 3.5)


def test_contract_quantiles_are_picked_from_a_wider_output() -> None:
    levels = (0.05, 0.1, 0.5, 0.9, 0.95)
    forecast = QuantileForecast(levels, ((0.0, 1.0, 2.0, 3.0, 4.0),))

    (point,) = to_forecast_points(forecast, FIRST_DAY, BOGOTA)

    assert (point.p10, point.p50, point.p90) == (1.0, 2.0, 3.0)


def test_crossed_quantiles_are_sorted_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    forecast = QuantileForecast(LEVELS, ((2.2, 2.0, 1.8),))

    with caplog.at_level(logging.WARNING):
        (point,) = to_forecast_points(forecast, FIRST_DAY, BOGOTA)

    assert (point.p10, point.p50, point.p90) == (1.8, 2.0, 2.2)
    assert "Crossed quantiles reordered" in caplog.text
    assert "2.2" not in caplog.text


def test_missing_contract_quantile_is_an_output_error() -> None:
    forecast = QuantileForecast((0.1, 0.9), ((1.0, 2.0),))

    with pytest.raises(ForecasterOutputError):
        to_forecast_points(forecast, FIRST_DAY, BOGOTA)


def result_with(points: tuple[ForecastPoint, ...]) -> ForecastResult:
    return ForecastResult("model", "1", datetime.now(BOGOTA), None, points)


def point_on(
    day: date, p10: float = 1.0, p50: float = 2.0, p90: float = 3.0
) -> ForecastPoint:
    return ForecastPoint(
        datetime.combine(day, datetime.min.time(), BOGOTA), p10, p50, p90
    )


def test_valid_result_passes() -> None:
    points = (point_on(FIRST_DAY), point_on(FIRST_DAY + timedelta(days=1)))

    validate_result(result_with(points), FIRST_DAY, 2, BOGOTA)


@pytest.mark.parametrize(
    "points, prediction_length",
    [
        ((point_on(FIRST_DAY),), 2),
        ((point_on(FIRST_DAY + timedelta(days=1)),), 1),
        ((point_on(FIRST_DAY), point_on(FIRST_DAY + timedelta(days=2))), 2),
        ((point_on(FIRST_DAY, p10=float("nan")),), 1),
        ((point_on(FIRST_DAY, p10=2.5),), 1),
        (
            (ForecastPoint(datetime(2026, 10, 10, 6, tzinfo=BOGOTA), 1.0, 2.0, 3.0),),
            1,
        ),
    ],
    ids=["count", "first-day", "skipped-day", "nan", "crossed", "not-midnight"],
)
def test_broken_results_are_rejected(
    points: tuple[ForecastPoint, ...], prediction_length: int
) -> None:
    with pytest.raises(ForecasterOutputError):
        validate_result(result_with(points), FIRST_DAY, prediction_length, BOGOTA)
