from uuid import UUID

from caudal_ia.insights.schemas import (
    AutopilotMode,
    Recommendation,
    RecommendationAction,
    ScheduleStatus,
    Severity,
    Snapshot,
    ValveSnapshot,
    ValveState,
)

RULES_MODEL = "rules-v1"
MAX_CLOSES_AT_FLOOR = 2
MAX_INSPECTED_ANOMALIES = 2
PERCENT = 100.0
CONFIDENCE_FLOOR_CLOSE = 0.9
CONFIDENCE_SCHEDULE = 0.8
CONFIDENCE_WAIT = 0.7
CONFIDENCE_INSPECT = 0.6


class RulesAdvisor:
    """Deterministic fallback (Strategy) used when the LLM is off or fails."""

    def __init__(self, open_margin_pct: float) -> None:
        self._open_margin_pct = open_margin_pct

    def recommend(self, snapshot: Snapshot) -> tuple[str, list[Recommendation]]:
        """Return a short summary and recommendations, most important first."""
        level = snapshot.tank.level_pct
        floor = snapshot.reserve_floor_pct
        recommendations: list[Recommendation] = []

        if level <= floor:
            recommendations += self._close_at_floor(snapshot)
            recommendations.append(
                _wait(
                    f"El tanque está en {level:.0f} %, en o bajo el piso de "
                    f"reserva ({floor:.0f} %): no se debe abrir ninguna llave."
                )
            )
        else:
            recommendations += self._follow_schedule(snapshot)

        recommendations += self._inspect(snapshot)
        if not recommendations:
            recommendations.append(
                _wait("No hay turnos activos ni alertas: se mantiene el estado actual.")
            )

        summary = (
            f"Tanque al {level:.0f} % con piso de reserva de {floor:.0f} % "
            f"(modo {_mode_label(snapshot.mode)}). Recomendaciones generadas por "
            "reglas, sin modelo de lenguaje."
        )
        return summary, recommendations

    def _close_at_floor(self, snapshot: Snapshot) -> list[Recommendation]:
        open_valves = sorted(
            (v for v in snapshot.valves if _is_commandable(v, ValveState.OPEN)),
            key=lambda valve: valve.priority,
            reverse=True,
        )
        return [
            Recommendation(
                action=RecommendationAction.CLOSE,
                valve_id=valve.id,
                reason=f"Cerrar la llave del sector {valve.sector_name} para "
                "proteger la reserva del tanque.",
                confidence=CONFIDENCE_FLOOR_CLOSE,
            )
            for valve in open_valves[:MAX_CLOSES_AT_FLOOR]
        ]

    def _follow_schedule(self, snapshot: Snapshot) -> list[Recommendation]:
        now = snapshot.generated_at
        active = {
            entry.sector_id
            for entry in snapshot.schedule
            if entry.status is ScheduleStatus.PLANNED
            and entry.starts_at <= now < entry.ends_at
        }
        ended = {
            entry.sector_id
            for entry in snapshot.schedule
            if entry.ends_at <= now and entry.status is not ScheduleStatus.SKIPPED
        } - active
        can_open, blocked_reason = self._can_open(snapshot)

        recommendations: list[Recommendation] = []
        for valve in sorted(snapshot.valves, key=lambda item: item.priority):
            if valve.sector_id in ended and _is_commandable(valve, ValveState.OPEN):
                recommendations.append(
                    Recommendation(
                        action=RecommendationAction.CLOSE,
                        valve_id=valve.id,
                        reason=f"El turno del sector {valve.sector_name} ya "
                        "terminó y la llave sigue abierta.",
                        confidence=CONFIDENCE_SCHEDULE,
                    )
                )
            elif valve.sector_id in active and _is_commandable(
                valve, ValveState.CLOSED
            ):
                recommendations.append(
                    _open(valve) if can_open else _wait(blocked_reason)
                )
        return _dedupe_waits(recommendations)

    def _can_open(self, snapshot: Snapshot) -> tuple[bool, str]:
        level = snapshot.tank.level_pct
        floor = snapshot.reserve_floor_pct
        if level <= floor + self._open_margin_pct:
            return False, (
                f"El tanque está en {level:.0f} %, muy cerca del piso de "
                f"reserva ({floor:.0f} %): conviene esperar antes de abrir."
            )
        max_level = snapshot.tank.max_level_m
        if snapshot.forecast:
            lowest_p10 = min(point.p10 for point in snapshot.forecast)
            if lowest_p10 / max_level * PERCENT <= floor:
                return False, (
                    "El pronóstico pesimista (p10) bajaría el tanque del "
                    f"piso de reserva ({floor:.0f} %): conviene esperar."
                )
        return True, ""

    def _inspect(self, snapshot: Snapshot) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        seen: set[str] = set()
        for anomaly in snapshot.anomalies:
            if anomaly.severity is Severity.HIGH and anomaly.kind not in seen:
                seen.add(anomaly.kind)
                recommendations.append(
                    Recommendation(
                        action=RecommendationAction.INSPECT,
                        valve_id=None,
                        reason=f"Hay una anomalía de severidad alta "
                        f"({anomaly.kind}): revisar en terreno.",
                        confidence=CONFIDENCE_INSPECT,
                    )
                )
            if len(seen) >= MAX_INSPECTED_ANOMALIES:
                break
        unknown = next(
            (v for v in snapshot.valves if v.state is ValveState.UNKNOWN), None
        )
        if unknown is not None:
            recommendations.append(
                Recommendation(
                    action=RecommendationAction.INSPECT,
                    valve_id=unknown.id,
                    reason=f"No se conoce el estado de la llave del sector "
                    f"{unknown.sector_name}: verificarla.",
                    confidence=CONFIDENCE_INSPECT,
                )
            )
        return recommendations


def _is_commandable(valve: ValveSnapshot, state: ValveState) -> bool:
    return valve.is_motorized and valve.state is state


def _open(valve: ValveSnapshot) -> Recommendation:
    return Recommendation(
        action=RecommendationAction.OPEN,
        valve_id=valve.id,
        reason=f"Es el turno del sector {valve.sector_name} y el tanque tiene "
        "reserva suficiente.",
        confidence=CONFIDENCE_SCHEDULE,
    )


def _wait(reason: str) -> Recommendation:
    return Recommendation(
        action=RecommendationAction.WAIT,
        valve_id=None,
        reason=reason,
        confidence=CONFIDENCE_WAIT,
    )


def _dedupe_waits(recommendations: list[Recommendation]) -> list[Recommendation]:
    """Keep a single WAIT when several valves are blocked for the same reason."""
    result: list[Recommendation] = []
    seen_reasons: set[tuple[RecommendationAction, UUID | None, str]] = set()
    for item in recommendations:
        key = (item.action, item.valve_id, item.reason)
        if item.action is RecommendationAction.WAIT and key in seen_reasons:
            continue
        seen_reasons.add(key)
        result.append(item)
    return result


def _mode_label(mode: AutopilotMode) -> str:
    return {
        AutopilotMode.MANUAL: "manual",
        AutopilotMode.ASSISTED: "asistido",
        AutopilotMode.AUTOMATIC: "automático",
    }[mode]
