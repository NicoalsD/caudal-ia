from http import HTTPStatus

from fastapi import APIRouter, Request

from caudal_ia.errors import MODEL_NOT_READY, RETRY_AFTER_SECONDS, ApiError

router = APIRouter(prefix="/v1")
MODEL_NOT_READY_MESSAGE = "El modelo aún no está listo para atender solicitudes."


@router.get(
    "/health",
    summary="Consultar la salud del servicio",
    description="Confirma que el servicio está activo sin exponer el modelo.",
)
def get_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Consultar la disponibilidad del modelo",
    description="Confirma si el modelo está cargado y listo para atender tráfico.",
    response_model=None,
    responses={
        HTTPStatus.SERVICE_UNAVAILABLE: {"description": "El modelo no está listo."}
    },
)
def get_readiness(request: Request) -> dict[str, str | bool]:
    readiness = request.app.state.readiness
    if readiness.is_loaded:
        return {"status": "ready", "model_loaded": True}

    raise ApiError(
        HTTPStatus.SERVICE_UNAVAILABLE,
        MODEL_NOT_READY,
        MODEL_NOT_READY_MESSAGE,
        {"model_name": readiness.model_name},
        headers={"Retry-After": RETRY_AFTER_SECONDS},
    )
