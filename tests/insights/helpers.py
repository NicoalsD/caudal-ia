from typing import Any

AQUEDUCT_ID = "0190f3a2-0000-7000-8000-000000000001"
TANK_ID = "0190f3a2-0000-7000-8000-000000000002"
VALVE_HIGH_ID = "0190f3a2-0000-7000-8000-0000000000a1"
VALVE_LOW_ID = "0190f3a2-0000-7000-8000-0000000000a2"
SECTOR_HIGH_ID = "0190f3a2-0000-7000-8000-0000000000b1"
SECTOR_LOW_ID = "0190f3a2-0000-7000-8000-0000000000b2"
UNKNOWN_VALVE_ID = "0190f3a2-0000-7000-8000-0000000000ff"


def make_snapshot(level_pct: float = 72.0, floor: float = 25.0) -> dict[str, Any]:
    return {
        "aqueduct_id": AQUEDUCT_ID,
        "aqueduct_name": "Vereda demo",
        "generated_at": "2026-11-07T10:00:00-05:00",
        "mode": "ASSISTED",
        "reserve_floor_pct": floor,
        "operator_last_action_at": None,
        "tank": {
            "id": TANK_ID,
            "name": "Tanque principal",
            "level_m": 2.5 * level_pct / 100,
            "max_level_m": 2.5,
            "level_pct": level_pct,
            "band": "HIGH",
            "observed_at": "2026-11-07T09:55:00-05:00",
            "trend": "STABLE",
        },
        "forecast": [
            {
                "timestamp": "2026-11-08T10:00:00-05:00",
                "p10": 1.6,
                "p50": 1.8,
                "p90": 2.0,
            }
        ],
        "valves": [
            {
                "id": VALVE_HIGH_ID,
                "sector_id": SECTOR_HIGH_ID,
                "sector_name": "Alto",
                "region_name": "Norte",
                "state": "CLOSED",
                "is_motorized": True,
                "priority": 1,
            },
            {
                "id": VALVE_LOW_ID,
                "sector_id": SECTOR_LOW_ID,
                "sector_name": "Bajo",
                "region_name": None,
                "state": "OPEN",
                "is_motorized": True,
                "priority": 2,
            },
        ],
        "schedule": [
            {
                "sector_id": SECTOR_HIGH_ID,
                "starts_at": "2026-11-07T09:30:00-05:00",
                "ends_at": "2026-11-07T11:00:00-05:00",
                "status": "PLANNED",
            }
        ],
        "anomalies": [],
    }


def llm_recommendations(*items: dict[str, Any]) -> dict[str, Any]:
    return {"summary": "Resumen del modelo.", "recommendations": list(items)}


def llm_item(
    action: str, valve_id: str | None, reason: str = "Motivo."
) -> dict[str, Any]:
    return {"action": action, "valve_id": valve_id, "reason": reason, "confidence": 0.8}
