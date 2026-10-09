from fastapi import FastAPI

from caudal_ia.config import get_settings
from caudal_ia.readiness import DEFAULT_MODEL_NAME, ModelReadiness
from caudal_ia.routes.health import router as health_router

settings = get_settings()

app = FastAPI(
    title="caudal-ia",
    description="Servicio de pronóstico del nivel del tanque de agua.",
    version="0.1.0",
    docs_url="/docs" if settings.api_docs_enabled else None,
)
app.state.readiness = ModelReadiness(DEFAULT_MODEL_NAME)
app.include_router(health_router)
