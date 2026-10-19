from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ForecastPoint:
    timestamp: datetime
    p10: float
    p50: float
    p90: float


@dataclass(frozen=True)
class ForecastResult:
    model_name: str
    model_version: str
    generated_at: datetime
    notes: str | None
    points: tuple[ForecastPoint, ...]
