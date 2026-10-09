from fastapi import FastAPI

app = FastAPI(
    title="caudal-ia",
    description="Servicio de pronóstico del nivel del tanque de agua.",
    version="0.1.0",
)
