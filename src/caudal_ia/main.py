from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from caudal_ia.body_limit import BodyLimitMiddleware
from caudal_ia.config import get_settings
from caudal_ia.errors import register_exception_handlers
from caudal_ia.forecasting.creator import ChronosForecasterCreator, ForecasterCreator
from caudal_ia.model_loading import start_model_loading
from caudal_ia.model_registry import resolve_active_model
from caudal_ia.readiness import ModelReadiness
from caudal_ia.routes.forecasts import router as forecasts_router
from caudal_ia.routes.health import router as health_router
from caudal_ia.routes.models import router as models_router

settings = get_settings()
active_spec = resolve_active_model(settings)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    creator: ForecasterCreator = getattr(
        application.state, "forecaster_creator", ChronosForecasterCreator()
    )
    start_model_loading(active_spec, creator, settings, application.state.readiness)
    yield


app = FastAPI(
    title="caudal-ia",
    description="Servicio de pronóstico del nivel del tanque de agua.",
    version="0.1.0",
    docs_url="/docs" if settings.api_docs_enabled else None,
    lifespan=lifespan,
)
register_exception_handlers(app)
app.add_middleware(BodyLimitMiddleware)
app.state.readiness = ModelReadiness(active_spec.name)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(forecasts_router)
