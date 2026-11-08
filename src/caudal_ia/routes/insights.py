from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from caudal_ia.auth import require_service_token
from caudal_ia.config import Settings, get_settings
from caudal_ia.insights.llm import (
    LlmClient,
    LlmClientConfig,
    OpenAiCompatibleClient,
)
from caudal_ia.insights.rules import RulesAdvisor
from caudal_ia.insights.schemas import (
    AskRequest,
    AskResponse,
    RecommendationsRequest,
    RecommendationsResponse,
    ReportRequest,
    ReportResponse,
)
from caudal_ia.insights.service import InsightsService

router = APIRouter(
    prefix="/v1/insights",
    tags=["insights"],
    dependencies=[Depends(require_service_token)],
)

COMMON_RESPONSES: dict[int | str, dict[str, str]] = {
    HTTPStatus.BAD_REQUEST: {"description": "La petición no cumple el contrato."},
    HTTPStatus.UNAUTHORIZED: {
        "description": "Falta el token de servicio o no es válido."
    },
    HTTPStatus.REQUEST_ENTITY_TOO_LARGE: {"description": "El cuerpo supera el límite."},
}


def build_llm_client(settings: Settings) -> LlmClient | None:
    """Factory: the OpenAI-compatible client, or None when there is no API key."""
    if settings.llm_api_key is None:
        return None
    return OpenAiCompatibleClient(
        LlmClientConfig(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            max_output_tokens=settings.llm_max_output_tokens,
            max_response_bytes=settings.llm_max_response_bytes,
            temperature=settings.llm_temperature,
        )
    )


def get_insights_service(request: Request) -> InsightsService:
    """Build the service; tests set `app.state.llm_client` to a fake LLM."""
    settings = get_settings()
    llm: LlmClient | None
    if hasattr(request.app.state, "llm_client"):
        llm = request.app.state.llm_client
    else:
        llm = build_llm_client(settings)
    return InsightsService(llm, RulesAdvisor(settings.assistant_open_margin_pct))


ServiceDependency = Annotated[InsightsService, Depends(get_insights_service)]


@router.post(
    "/recommendations",
    summary="Recomendar acciones sobre las llaves",
    description=(
        "Recibe el estado del acueducto y devuelve hasta 5 recomendaciones. "
        "Usa un LLM si hay LLM_API_KEY y, si falla o no hay clave, reglas "
        "deterministas (`source: RULES`). Nunca recomienda OPEN con el tanque "
        "en o bajo el piso de reserva. No guarda datos."
    ),
    response_model=RecommendationsResponse,
    responses=COMMON_RESPONSES,
)
def create_recommendations(
    body: RecommendationsRequest, service: ServiceDependency
) -> RecommendationsResponse:
    return service.recommend(body.snapshot)


@router.post(
    "/report",
    summary="Redactar el informe de un periodo",
    description=(
        "Convierte los agregados del periodo en un informe en español. Sin LLM "
        "usa una plantilla (`source: RULES`)."
    ),
    response_model=ReportResponse,
    responses=COMMON_RESPONSES,
)
def create_report(body: ReportRequest, service: ServiceDependency) -> ReportResponse:
    return service.report(body)


@router.post(
    "/ask",
    summary="Responder una pregunta sobre el estado",
    description=(
        "Responde una pregunta de hasta 500 caracteres con base en el estado "
        "del acueducto. Sin LLM devuelve un resumen del estado (`source: RULES`)."
    ),
    response_model=AskResponse,
    responses=COMMON_RESPONSES,
)
def create_answer(body: AskRequest, service: ServiceDependency) -> AskResponse:
    return service.ask(body)
