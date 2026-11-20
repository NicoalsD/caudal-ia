import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError

from caudal_ia.insights import prompts
from caudal_ia.insights.guard import enforce_guards, truncate_reason
from caudal_ia.insights.llm import LlmClient, LlmError
from caudal_ia.insights.rules import RULES_MODEL, RulesAdvisor
from caudal_ia.insights.schemas import (
    MAX_ANSWER_LENGTH,
    MAX_REPORT_FINDINGS,
    AskRequest,
    AskResponse,
    InsightSource,
    LlmAskOutput,
    LlmRecommendationsOutput,
    LlmReportOutput,
    Recommendation,
    RecommendationsResponse,
    ReportRequest,
    ReportResponse,
    Snapshot,
)

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]
SCALAR_TYPES = (int, float, str, bool)


def utc_now() -> datetime:
    return datetime.now(UTC)


class InsightsService:
    """Template Method for the three insights: try the LLM, else use RULES."""

    def __init__(
        self,
        llm: LlmClient | None,
        advisor: RulesAdvisor,
        clock: Clock = utc_now,
    ) -> None:
        self._llm = llm
        self._advisor = advisor
        self._clock = clock

    def recommend(self, snapshot: Snapshot) -> RecommendationsResponse:
        generated_at = self._clock()
        output = self._ask_llm(
            prompts.RECOMMENDATIONS_SYSTEM,
            prompts.recommendations_user_prompt(_to_json(snapshot)),
            LlmRecommendationsOutput,
        )
        if self._llm is not None and output is not None:
            recommendations = enforce_guards(
                _convert_llm_recommendations(output), snapshot
            )
            if recommendations:
                return RecommendationsResponse(
                    source=InsightSource.LLM,
                    model=self._llm.model,
                    generated_at=generated_at,
                    summary=output.summary,
                    recommendations=recommendations,
                )
            logger.warning("LLM recommendations were all discarded by the guards")

        summary, rules_output = self._advisor.recommend(snapshot)
        # The same guards apply to the deterministic output.
        return RecommendationsResponse(
            source=InsightSource.RULES,
            model=RULES_MODEL,
            generated_at=generated_at,
            summary=summary,
            recommendations=enforce_guards(rules_output, snapshot),
        )

    def report(self, request: ReportRequest) -> ReportResponse:
        generated_at = self._clock()
        report_input = {
            "aqueduct_name": request.aqueduct_name,
            "from": request.from_.isoformat(),
            "to": request.to.isoformat(),
            "aggregates": request.aggregates,
        }
        output = self._ask_llm(
            prompts.REPORT_SYSTEM,
            prompts.report_user_prompt(report_input),
            LlmReportOutput,
        )
        if self._llm is not None and output is not None:
            source, model = InsightSource.LLM, self._llm.model
        else:
            output = _template_report(request)
            source, model = InsightSource.RULES, RULES_MODEL
        return ReportResponse(
            source=source,
            model=model,
            generated_at=generated_at,
            title=output.title,
            summary=output.summary,
            findings=output.findings,
            recommendations=output.recommendations,
            markdown=_report_markdown(request, output),
        )

    def ask(self, request: AskRequest) -> AskResponse:
        generated_at = self._clock()
        output = self._ask_llm(
            prompts.ASK_SYSTEM,
            prompts.ask_user_prompt(request.question, _to_json(request.snapshot)),
            LlmAskOutput,
        )
        if self._llm is not None and output is not None:
            return AskResponse(
                source=InsightSource.LLM,
                model=self._llm.model,
                generated_at=generated_at,
                answer=output.answer,
            )
        return AskResponse(
            source=InsightSource.RULES,
            model=RULES_MODEL,
            generated_at=generated_at,
            answer=_template_answer(request.snapshot),
        )

    def _ask_llm[T: BaseModel](
        self, system: str, user: str, output_type: type[T]
    ) -> T | None:
        """Return the validated LLM output, or None when RULES must be used."""
        if self._llm is None:
            return None
        try:
            return output_type.model_validate(self._llm.complete_json(system, user))
        except LlmError as error:
            logger.warning("LLM unavailable, using RULES: %s", error)
        except ValidationError as error:
            logger.warning(
                "LLM output rejected, using RULES (%d errors)", error.error_count()
            )
        return None


def _to_json(snapshot: Snapshot) -> dict[str, Any]:
    return snapshot.model_dump(mode="json")


def _convert_llm_recommendations(
    output: LlmRecommendationsOutput,
) -> list[Recommendation]:
    converted: list[Recommendation] = []
    for item in output.recommendations:
        valve_id: UUID | None = None
        if item.valve_id is not None:
            try:
                valve_id = UUID(item.valve_id)
            except ValueError:
                continue  # Not a valid id, so it cannot be a known valve.
        converted.append(
            Recommendation(
                action=item.action,
                valve_id=valve_id,
                reason=truncate_reason(item.reason),
                confidence=item.confidence,
            )
        )
    return converted


def _template_report(request: ReportRequest) -> LlmReportOutput:
    findings = [
        f"{key}: {value}"[:500]
        for key, value in request.aggregates.items()
        if isinstance(value, SCALAR_TYPES)
    ][:MAX_REPORT_FINDINGS]
    period = f"{request.from_.date().isoformat()} a {request.to.date().isoformat()}"
    return LlmReportOutput(
        title=f"Informe de {request.aqueduct_name} ({period})",
        summary=(
            f"Resumen automático del periodo {period} con "
            f"{len(request.aggregates)} agregados recibidos. Se generó con "
            "plantillas porque el asistente de IA no está disponible."
        ),
        findings=findings,
        recommendations=[
            "Revisar los agregados del periodo con la Junta y definir los "
            "ajustes de turnos que haga falta."
        ],
    )


def _report_markdown(request: ReportRequest, output: LlmReportOutput) -> str:
    lines = [f"# {output.title}", "", output.summary, ""]
    lines += ["## Hallazgos", "", *[f"- {item}" for item in output.findings], ""]
    lines += [
        "## Recomendaciones",
        "",
        *[f"- {item}" for item in output.recommendations],
        "",
    ]
    lines.append(f"Periodo: {request.from_.isoformat()} a {request.to.isoformat()}.")
    return "\n".join(lines)


def _template_answer(snapshot: Snapshot) -> str:
    tank = snapshot.tank
    answer = (
        f"El tanque {tank.name} está al {tank.level_pct:.0f} % "
        f"({tank.level_m:.2f} m de {tank.max_level_m:.2f} m), con un piso de "
        f"reserva de {snapshot.reserve_floor_pct:.0f} %. El acueducto está en "
        f"modo {snapshot.mode.value}. El asistente de IA no está disponible, así "
        "que esta es una lectura automática del estado y no responde la pregunta "
        "en detalle."
    )
    return answer[:MAX_ANSWER_LENGTH]
