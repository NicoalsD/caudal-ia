from uuid import UUID

from caudal_ia.insights.schemas import (
    MAX_REASON_LENGTH,
    MAX_RECOMMENDATIONS,
    Recommendation,
    RecommendationAction,
    Snapshot,
)

TRUNCATION_MARK = "..."


def truncate_reason(reason: str) -> str:
    """Cut a reason to the contract limit."""
    if len(reason) <= MAX_REASON_LENGTH:
        return reason
    return reason[: MAX_REASON_LENGTH - len(TRUNCATION_MARK)] + TRUNCATION_MARK


def is_at_or_below_floor(snapshot: Snapshot) -> bool:
    return snapshot.tank.level_pct <= snapshot.reserve_floor_pct


def enforce_guards(
    recommendations: list[Recommendation], snapshot: Snapshot
) -> list[Recommendation]:
    """Apply the hard rules to any recommendation list (LLM or rules).

    - Drop recommendations about valves that are not in the snapshot.
    - Drop OPEN and CLOSE without a valve.
    - Drop OPEN when the tank is at or below the reserve floor.
    - Keep at most MAX_RECOMMENDATIONS.
    """
    known_valves: set[UUID] = {valve.id for valve in snapshot.valves}
    at_floor = is_at_or_below_floor(snapshot)
    allowed: list[Recommendation] = []
    for recommendation in recommendations:
        action = recommendation.action
        if recommendation.valve_id is not None:
            if recommendation.valve_id not in known_valves:
                continue
        elif action in (RecommendationAction.OPEN, RecommendationAction.CLOSE):
            continue
        if action is RecommendationAction.OPEN and at_floor:
            continue
        allowed.append(recommendation)
    return allowed[:MAX_RECOMMENDATIONS]
