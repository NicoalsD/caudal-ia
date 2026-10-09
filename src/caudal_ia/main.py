from fastapi import FastAPI

from caudal_ia.config import get_settings

settings = get_settings()

app = FastAPI(
    title="caudal-ia",
    description="Servicio de pronóstico del nivel del tanque de agua.",
    version="0.1.0",
    docs_url="/docs" if settings.api_docs_enabled else None,
)
