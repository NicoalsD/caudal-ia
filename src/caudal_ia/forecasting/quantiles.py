import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from caudal_ia.domain import ForecastPoint
from caudal_ia.forecasting.forecaster import ForecasterOutputError, QuantileForecast

logger = logging.getLogger(__name__)

P10_LEVEL = 0.1
P50_LEVEL = 0.5
P90_LEVEL = 0.9
CONTRACT_QUANTILE_LEVELS = (P10_LEVEL, P50_LEVEL, P90_LEVEL)
ONE_DAY = timedelta(days=1)


def to_forecast_points(
    forecast: QuantileForecast,
    first_day: date,
    timezone: ZoneInfo,
) -> tuple[ForecastPoint, ...]:
    """Turn model quantiles into p10, p50 and p90 points at local midnight.

    Step ``n`` is the day ``first_day + n``. If the model crosses its quantiles,
    they are sorted so that ``p10 <= p50 <= p90`` and the fix is logged without
    the values.
    """
    try:
        positions = [
            forecast.quantile_levels.index(level) for level in CONTRACT_QUANTILE_LEVELS
        ]
    except ValueError as error:
        raise ForecasterOutputError(
            "The model did not return p10, p50 and p90."
        ) from error

    points: list[ForecastPoint] = []
    for step, quantiles in enumerate(forecast.steps):
        selected = [quantiles[position] for position in positions]
        p10, p50, p90 = sorted(selected)
        if [p10, p50, p90] != selected:
            logger.warning("Crossed quantiles reordered step=%d", step)
        day = first_day + step * ONE_DAY
        points.append(
            ForecastPoint(
                timestamp=datetime.combine(day, time.min, tzinfo=timezone),
                p10=p10,
                p50=p50,
                p90=p90,
            )
        )
    return tuple(points)
