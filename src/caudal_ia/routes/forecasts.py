from http import HTTPStatus

from fastapi import APIRouter, Request

from caudal_ia.config import get_settings
from caudal_ia.errors import (
    INTERNAL_ERROR,
    MODEL_NOT_READY,
    RETRY_AFTER_SECONDS,
    ApiError,
)
from caudal_ia.request_validation import (
    validate_prediction_length,
    validate_quantile_levels,
)
from caudal_ia.schemas import ForecastRequest
from caudal_ia.series_validation import validate_series

router = APIRouter(prefix="/v1")

MODEL_NOT_READY_MESSAGE = "El modelo aún no está listo para atender solicitudes."
INFERENCE_NOT_IMPLEMENTED_MESSAGE = "La inferencia aún no está implementada."


@router.post(
    "/forecasts",
    summary="Generar un pronóstico",
    description="Valida una serie diaria y genera un pronóstico del nivel del tanque.",
    response_model=None,
    responses={
        HTTPStatus.BAD_REQUEST: {"description": "La petición no cumple el contrato."},
        HTTPStatus.REQUEST_ENTITY_TOO_LARGE: {
            "description": "El cuerpo supera el límite."
        },
        HTTPStatus.UNPROCESSABLE_ENTITY: {
            "description": "La serie no puede usarse para pronosticar."
        },
        HTTPStatus.SERVICE_UNAVAILABLE: {"description": "El modelo no está listo."},
        HTTPStatus.INTERNAL_SERVER_ERROR: {
            "description": "Error interno del servicio."
        },
    },
)
def create_forecast(request: Request, forecast_request: ForecastRequest) -> None:
    settings = get_settings()
    validate_prediction_length(forecast_request.prediction_length, settings)
    validate_quantile_levels(forecast_request.quantile_levels)
    validate_series(forecast_request.timestamps, forecast_request.values, settings)

    readiness = request.app.state.readiness
    if not readiness.is_loaded:
        raise ApiError(
            HTTPStatus.SERVICE_UNAVAILABLE,
            MODEL_NOT_READY,
            MODEL_NOT_READY_MESSAGE,
            {"model_name": readiness.model_name},
            headers={"Retry-After": RETRY_AFTER_SECONDS},
        )

    raise ApiError(
        HTTPStatus.INTERNAL_SERVER_ERROR,
        INTERNAL_ERROR,
        INFERENCE_NOT_IMPLEMENTED_MESSAGE,
        {},
    )
