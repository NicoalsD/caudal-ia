import math
from datetime import datetime

from caudal_ia.config import Settings

LENGTH_MISMATCH = "LENGTH_MISMATCH"
TOO_MANY_POINTS = "TOO_MANY_POINTS"
TIMESTAMP_PARSE_ERROR = "TIMESTAMP_PARSE_ERROR"
TIMESTAMPS_NOT_INCREASING = "TIMESTAMPS_NOT_INCREASING"
NOT_FINITE_VALUE = "NOT_FINITE_VALUE"
FIRST_TIMESTAMP_INDEX = 1

_ERROR_MESSAGES = {
    LENGTH_MISMATCH: (
        "Las marcas de tiempo y los valores deben tener la misma longitud."
    ),
    TOO_MANY_POINTS: "La serie supera la cantidad máxima de puntos permitida.",
    TIMESTAMP_PARSE_ERROR: "Una marca de tiempo no es ISO-8601 válida o no tiene zona.",
    TIMESTAMPS_NOT_INCREASING: (
        "Las marcas de tiempo deben ser estrictamente crecientes."
    ),
    NOT_FINITE_VALUE: "La serie tiene un valor que no es un número finito.",
}


class SeriesValidationError(Exception):
    def __init__(self, reason: str, index: int | None) -> None:
        self.reason = reason
        self.index = index
        message = _ERROR_MESSAGES[reason]
        if index is not None:
            message = f"{message} Índice: {index}."
        super().__init__(message)


class InsufficientHistoryError(Exception):
    def __init__(self, received: int, minimum: int) -> None:
        self.received = received
        self.minimum = minimum
        super().__init__(
            f"La serie tiene {received} puntos; se requieren al menos {minimum}."
        )


def validate_series(
    timestamps: list[str],
    values: list[float],
    settings: Settings,
) -> None:
    if len(timestamps) != len(values):
        raise SeriesValidationError(LENGTH_MISMATCH, None)

    if len(values) > settings.max_series_points:
        raise SeriesValidationError(TOO_MANY_POINTS, settings.max_series_points)

    parsed_timestamps: list[datetime] = []
    for index, timestamp in enumerate(timestamps):
        try:
            parsed_timestamp = datetime.fromisoformat(timestamp)
        except ValueError as error:
            raise SeriesValidationError(TIMESTAMP_PARSE_ERROR, index) from error
        if parsed_timestamp.tzinfo is None:
            raise SeriesValidationError(TIMESTAMP_PARSE_ERROR, index)
        parsed_timestamps.append(parsed_timestamp)

    for index in range(FIRST_TIMESTAMP_INDEX, len(parsed_timestamps)):
        previous_index = index - FIRST_TIMESTAMP_INDEX
        if parsed_timestamps[index] <= parsed_timestamps[previous_index]:
            raise SeriesValidationError(TIMESTAMPS_NOT_INCREASING, index)

    for index, value in enumerate(values):
        if not math.isfinite(value):
            raise SeriesValidationError(NOT_FINITE_VALUE, index)

    if len(values) < settings.forecast_min_points:
        raise InsufficientHistoryError(
            received=len(values),
            minimum=settings.forecast_min_points,
        )
