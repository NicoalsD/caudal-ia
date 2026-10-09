from caudal_ia.config import Settings

MIN_PREDICTION_LENGTH = 1
SUPPORTED_QUANTILE_LEVELS = (0.1, 0.5, 0.9)

PREDICTION_LENGTH_OUT_OF_RANGE = "PREDICTION_LENGTH_OUT_OF_RANGE"
QUANTILE_LEVELS_NOT_SUPPORTED = "QUANTILE_LEVELS_NOT_SUPPORTED"

PREDICTION_LENGTH_FIELD = "prediction_length"
QUANTILE_LEVELS_FIELD = "quantile_levels"

_ERROR_MESSAGES = {
    PREDICTION_LENGTH_OUT_OF_RANGE: (
        "La longitud del pronóstico está fuera del rango permitido."
    ),
    QUANTILE_LEVELS_NOT_SUPPORTED: "Los cuantiles solicitados no están soportados.",
}


class ContractValidationError(Exception):
    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(_ERROR_MESSAGES[reason])


def validate_prediction_length(prediction_length: int, settings: Settings) -> None:
    if not MIN_PREDICTION_LENGTH <= prediction_length <= settings.max_prediction_length:
        raise ContractValidationError(
            PREDICTION_LENGTH_FIELD,
            PREDICTION_LENGTH_OUT_OF_RANGE,
        )


def validate_quantile_levels(quantile_levels: list[float]) -> None:
    if quantile_levels != list(SUPPORTED_QUANTILE_LEVELS):
        raise ContractValidationError(
            QUANTILE_LEVELS_FIELD,
            QUANTILE_LEVELS_NOT_SUPPORTED,
        )
