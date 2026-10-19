import math
from datetime import date, time, timedelta
from zoneinfo import ZoneInfo

from caudal_ia.domain import ForecastResult
from caudal_ia.forecasting.forecaster import ForecasterOutputError

ONE_DAY = timedelta(days=1)


def validate_result(
    result: ForecastResult,
    first_day: date,
    prediction_length: int,
    timezone: ZoneInfo,
) -> None:
    """Check the guarantees of the response contract before answering.

    There must be ``prediction_length`` points on consecutive local days starting
    at ``first_day``, each at local midnight, with finite ``p10 <= p50 <= p90``.
    The backend checks the same rules and would discard a broken answer, so a
    failure here is an internal error of the service.
    """
    if len(result.points) != prediction_length:
        raise ForecasterOutputError(
            f"Expected {prediction_length} points, got {len(result.points)}."
        )
    for step, point in enumerate(result.points):
        local = point.timestamp.astimezone(timezone)
        expected_day = first_day + step * ONE_DAY
        if local.date() != expected_day or local.time() != time.min:
            raise ForecasterOutputError(f"Point {step} is not the expected day.")
        quantiles = (point.p10, point.p50, point.p90)
        if not all(math.isfinite(value) for value in quantiles):
            raise ForecasterOutputError(f"Point {step} has a non-finite quantile.")
        if not point.p10 <= point.p50 <= point.p90:
            raise ForecasterOutputError(f"Point {step} has crossed quantiles.")
