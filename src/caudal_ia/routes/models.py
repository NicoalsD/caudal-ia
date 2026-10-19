from fastapi import APIRouter, Depends, Request

from caudal_ia.auth import require_service_token
from caudal_ia.config import get_settings
from caudal_ia.model_registry import ModelRegistry
from caudal_ia.schemas import ModelSpecResponse, ModelsResponse

router = APIRouter(prefix="/v1", dependencies=[Depends(require_service_token)])


@router.get(
    "/models",
    response_model=ModelsResponse,
    summary="Consultar los modelos disponibles",
    description="Lista los modelos disponibles e identifica el modelo activo.",
)
def get_models(request: Request) -> ModelsResponse:
    active_model_name = get_settings().chronos_model_id
    model_loaded = request.app.state.readiness.is_loaded
    return ModelsResponse(
        models=[
            ModelSpecResponse(
                name=spec.name,
                version=spec.version,
                loaded=spec.name == active_model_name and model_loaded,
                quantile_levels=list(spec.quantile_levels),
                max_prediction_length=spec.max_prediction_length,
                parameters_millions=spec.parameters_millions,
            )
            for spec in ModelRegistry.get_instance().list_specs()
        ],
        active=active_model_name,
    )
