from http import HTTPStatus
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/v1")
RETRY_AFTER_SECONDS = "30"


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
def get_readiness(request: Request) -> dict[str, str | bool] | JSONResponse:
    readiness = request.app.state.readiness
    if readiness.is_loaded:
        return {"status": "ready", "model_loaded": True}

    return JSONResponse(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        headers={"Retry-After": RETRY_AFTER_SECONDS},
        content={
            "error": {
                "code": "MODEL_NOT_READY",
                "message": "El modelo aún no está listo para atender solicitudes.",
                "details": {"model_name": readiness.model_name},
                "request_id": str(uuid4()),
            }
        },
    )
