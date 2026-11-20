import json
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

MAX_VALVES = 200
MAX_SCHEDULE_ENTRIES = 200
MAX_ANOMALIES = 100
MAX_FORECAST_POINTS = 400
MAX_RECOMMENDATIONS = 5
MAX_REASON_LENGTH = 280
MAX_QUESTION_LENGTH = 500
MAX_NAME_LENGTH = 200
MAX_AGGREGATES_BYTES = 32 * 1024
MAX_PERCENT = 100.0
MAX_REPORT_FINDINGS = 10
MAX_TITLE_LENGTH = 200
MAX_SUMMARY_LENGTH = 1000
MAX_ITEM_LENGTH = 500
MAX_ANSWER_LENGTH = 2000


class AutopilotMode(StrEnum):
    MANUAL = "MANUAL"
    ASSISTED = "ASSISTED"
    AUTOMATIC = "AUTOMATIC"


class TankBand(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    CRITICAL = "CRITICAL"


class Trend(StrEnum):
    RISING = "RISING"
    FALLING = "FALLING"
    STABLE = "STABLE"


class ValveState(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class ScheduleStatus(StrEnum):
    PLANNED = "PLANNED"
    DONE = "DONE"
    PARTIAL = "PARTIAL"
    SKIPPED = "SKIPPED"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RecommendationAction(StrEnum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    WAIT = "WAIT"
    INSPECT = "INSPECT"


class InsightSource(StrEnum):
    LLM = "LLM"
    RULES = "RULES"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TankSnapshot(StrictModel):
    id: UUID = Field(description="Identificador del tanque.")
    name: str = Field(max_length=MAX_NAME_LENGTH, description="Nombre del tanque.")
    level_m: float = Field(allow_inf_nan=False, description="Nivel en metros.")
    max_level_m: float = Field(
        gt=0, allow_inf_nan=False, description="Nivel máximo en metros."
    )
    level_pct: float = Field(
        ge=0, allow_inf_nan=False, description="Nivel como porcentaje del máximo."
    )
    band: TankBand | None = Field(default=None, description="Banda de nivel.")
    observed_at: AwareDatetime = Field(description="Momento de la última lectura.")
    trend: Trend | None = Field(default=None, description="Tendencia del nivel.")


class ForecastPoint(StrictModel):
    timestamp: AwareDatetime
    p10: float = Field(allow_inf_nan=False)
    p50: float = Field(allow_inf_nan=False)
    p90: float = Field(allow_inf_nan=False)


class ValveSnapshot(StrictModel):
    id: UUID
    sector_id: UUID
    sector_name: str = Field(max_length=MAX_NAME_LENGTH)
    region_name: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)
    state: ValveState
    is_motorized: bool = Field(description="Solo las motorizadas reciben comandos.")
    priority: int = Field(description="Un número menor indica mayor prioridad.")


class ScheduleEntry(StrictModel):
    sector_id: UUID
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    status: ScheduleStatus


class AnomalyEntry(StrictModel):
    kind: str = Field(max_length=MAX_NAME_LENGTH)
    severity: Severity


class Snapshot(StrictModel):
    aqueduct_id: UUID
    aqueduct_name: str = Field(max_length=MAX_NAME_LENGTH)
    generated_at: AwareDatetime
    mode: AutopilotMode
    reserve_floor_pct: float = Field(ge=0, le=MAX_PERCENT)
    operator_last_action_at: AwareDatetime | None = None
    tank: TankSnapshot
    forecast: list[ForecastPoint] = Field(
        default_factory=list, max_length=MAX_FORECAST_POINTS
    )
    valves: list[ValveSnapshot] = Field(default_factory=list, max_length=MAX_VALVES)
    schedule: list[ScheduleEntry] = Field(
        default_factory=list, max_length=MAX_SCHEDULE_ENTRIES
    )
    anomalies: list[AnomalyEntry] = Field(
        default_factory=list, max_length=MAX_ANOMALIES
    )


class RecommendationsRequest(StrictModel):
    snapshot: Snapshot


class Recommendation(StrictModel):
    action: RecommendationAction
    valve_id: UUID | None = Field(
        default=None, description="Llave afectada; nula para WAIT o INSPECT general."
    )
    reason: str = Field(
        min_length=1, max_length=MAX_REASON_LENGTH, description="Motivo en español."
    )
    confidence: float = Field(ge=0, le=1, description="Confianza de 0 a 1.")


class RecommendationsResponse(StrictModel):
    source: InsightSource = Field(description="Origen: LLM o RULES (respaldo).")
    model: str = Field(description="Modelo usado, o rules-v1 para el respaldo.")
    generated_at: datetime
    summary: str
    recommendations: list[Recommendation] = Field(max_length=MAX_RECOMMENDATIONS)


class ReportRequest(StrictModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    aqueduct_name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    from_: AwareDatetime = Field(alias="from")
    to: AwareDatetime
    aggregates: dict[str, Any] = Field(
        description="Agregados del periodo (objeto libre, máximo 32 KB)."
    )

    @field_validator("aggregates")
    @classmethod
    def limit_aggregates_size(cls, aggregates: dict[str, Any]) -> dict[str, Any]:
        """Reject aggregates whose JSON form is larger than the limit."""
        size = len(json.dumps(aggregates, ensure_ascii=False).encode("utf-8"))
        if size > MAX_AGGREGATES_BYTES:
            raise ValueError("Los agregados superan 32 KB.")
        return aggregates

    @model_validator(mode="after")
    def require_ordered_period(self) -> "ReportRequest":
        """Reject a period that ends before it starts."""
        if self.to < self.from_:
            raise ValueError("`to` no puede ser anterior a `from`.")
        return self


class ReportResponse(StrictModel):
    source: InsightSource
    model: str
    generated_at: datetime
    title: str
    summary: str
    findings: list[str]
    recommendations: list[str]
    markdown: str


class AskRequest(StrictModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)
    snapshot: Snapshot


class AskResponse(StrictModel):
    source: InsightSource
    model: str
    generated_at: datetime
    answer: str


# Shapes the LLM must return. Unknown fields or wrong types mean "invalid output".
class LlmRecommendation(StrictModel):
    action: RecommendationAction
    valve_id: str | None = None
    reason: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class LlmRecommendationsOutput(StrictModel):
    summary: str = Field(min_length=1, max_length=MAX_SUMMARY_LENGTH)
    recommendations: list[LlmRecommendation]


class LlmReportOutput(StrictModel):
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    summary: str = Field(min_length=1, max_length=MAX_SUMMARY_LENGTH)
    findings: list[str] = Field(max_length=MAX_REPORT_FINDINGS)
    recommendations: list[str] = Field(max_length=MAX_REPORT_FINDINGS)

    @field_validator("findings", "recommendations")
    @classmethod
    def limit_item_length(cls, items: list[str]) -> list[str]:
        if any(not item or len(item) > MAX_ITEM_LENGTH for item in items):
            raise ValueError("Elemento vacío o demasiado largo.")
        return items


class LlmAskOutput(StrictModel):
    answer: str = Field(min_length=1, max_length=MAX_ANSWER_LENGTH)
