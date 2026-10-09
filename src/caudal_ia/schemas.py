from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MODEL_NAME_MAX_LENGTH = 60
MODEL_VERSION_MAX_LENGTH = 40
MODEL_NOTES_MAX_LENGTH = 200
MAX_FORECAST_POINTS = 30


class ForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: UUID = Field(description="Identificador único de la serie.")
    timestamps: list[str] = Field(
        min_length=1,
        description="Marcas de tiempo de las lecturas, en formato ISO-8601.",
    )
    values: list[float] = Field(
        min_length=1,
        description="Valores observados de la serie.",
    )
    prediction_length: int = Field(description="Cantidad de días por pronosticar.")
    quantile_levels: list[float] = Field(
        description="Niveles de cuantiles solicitados para el pronóstico."
    )


class ModelInfo(BaseModel):
    name: str = Field(
        max_length=MODEL_NAME_MAX_LENGTH,
        description="Nombre del modelo utilizado.",
    )
    version: str = Field(
        max_length=MODEL_VERSION_MAX_LENGTH,
        description="Versión del modelo utilizado.",
    )
    notes: str | None = Field(
        default=None,
        max_length=MODEL_NOTES_MAX_LENGTH,
        description="Notas sobre el pronóstico o el procesamiento aplicado.",
    )


class ForecastPointResponse(BaseModel):
    timestamp: datetime = Field(description="Fecha y hora del punto pronosticado.")
    p10: float = Field(description="Cuantil 10 del nivel pronosticado.")
    p50: float = Field(description="Cuantil 50 del nivel pronosticado.")
    p90: float = Field(description="Cuantil 90 del nivel pronosticado.")


class ForecastResponse(BaseModel):
    model: ModelInfo = Field(description="Información del modelo utilizado.")
    generated_at: datetime = Field(
        description="Fecha y hora en que se generó el pronóstico."
    )
    frequency: Literal["D"] = Field(description="Frecuencia diaria del pronóstico.")
    points: list[ForecastPointResponse] = Field(
        min_length=1,
        max_length=MAX_FORECAST_POINTS,
        description="Puntos pronosticados con sus cuantiles.",
    )
