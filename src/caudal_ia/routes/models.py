from fastapi import APIRouter, Request

from caudal_ia.model_catalog import CHRONOS_MODEL_SPECS
from caudal_ia.readiness import DEFAULT_MODEL_NAME
from caudal_ia.schemas import ModelSpecResponse, ModelsResponse

router = APIRouter(prefix="/v1")


@router.get(
    "/models",
    response_model=ModelsResponse,
    summary="Consultar los modelos disponibles",
    description="Lista los modelos disponibles e identifica el modelo activo.",
)
def get_models(request: Request) -> ModelsResponse:
    model_loaded = request.app.state.readiness.is_loaded
    return ModelsResponse(
        models=[
            ModelSpecResponse(
                name=spec.name,
                version=spec.version,
                loaded=spec.name == DEFAULT_MODEL_NAME and model_loaded,
                quantile_levels=list(spec.quantile_levels),
                max_prediction_length=spec.max_prediction_length,
                parameters_millions=spec.parameters_millions,
            )
            for spec in CHRONOS_MODEL_SPECS
        ],
        active=DEFAULT_MODEL_NAME,
    )
