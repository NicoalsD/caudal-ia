from http import HTTPStatus

from fastapi import APIRouter, Depends, Request

from caudal_ia.adapters import ForecastResponseAdapter
from caudal_ia.auth import require_service_token
from caudal_ia.config import get_settings
from caudal_ia.errors import (
    MODEL_NOT_READY,
    RETRY_AFTER_SECONDS,
    ApiError,
)
from caudal_ia.forecasting.forecaster import Forecaster
from caudal_ia.forecasting.pipeline import ForecastInput, ServingForecastPipeline
from caudal_ia.model_registry import ModelNotLoadedError, ModelRegistry
from caudal_ia.request_validation import (
    validate_prediction_length,
    validate_quantile_levels,
)
from caudal_ia.schemas import ForecastRequest, ForecastResponse
from caudal_ia.series_validation import validate_series

router = APIRouter(prefix="/v1", dependencies=[Depends(require_service_token)])

MODEL_NOT_READY_MESSAGE = "El modelo aún no está listo para atender solicitudes."
response_adapter = ForecastResponseAdapter()


@router.post(
    "/forecasts",
    summary="Generar un pronóstico",
    description=(
        "Re-muestrea la serie a un valor por día en la zona del acueducto y "
        "devuelve los cuantiles p10, p50 y p90 de los días siguientes. "
        "No guarda la serie ni el pronóstico."
    ),
    response_model=ForecastResponse,
    responses={
        HTTPStatus.BAD_REQUEST: {"description": "La petición no cumple el contrato."},
        HTTPStatus.UNAUTHORIZED: {
            "description": "Falta el token de servicio o no es válido."
        },
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
def create_forecast(
    request: Request, forecast_request: ForecastRequest
) -> ForecastResponse:
    settings = get_settings()
    validate_prediction_length(forecast_request.prediction_length, settings)
    validate_quantile_levels(forecast_request.quantile_levels)
    validate_series(forecast_request.timestamps, forecast_request.values, settings)

    readiness = request.app.state.readiness

    def active_forecaster() -> Forecaster:
        try:
            if not readiness.is_loaded:
                raise ModelNotLoadedError(readiness.model_name)
            return ModelRegistry.get_instance().get_forecaster(readiness.model_name)
        except ModelNotLoadedError as error:
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                MODEL_NOT_READY,
                MODEL_NOT_READY_MESSAGE,
                {"model_name": readiness.model_name},
                headers={"Retry-After": RETRY_AFTER_SECONDS},
            ) from error

    pipeline = ServingForecastPipeline(active_forecaster, settings)
    result = pipeline.run(
        ForecastInput(
            timestamps=forecast_request.timestamps,
            values=forecast_request.values,
            prediction_length=forecast_request.prediction_length,
            quantile_levels=forecast_request.quantile_levels,
        )
    )
    return response_adapter.to_response(result)
