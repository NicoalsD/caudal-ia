from collections.abc import Callable
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient

from caudal_ia.insights.llm import LlmError
from tests.fakes import FakeLlmClient
from tests.insights.helpers import (
    UNKNOWN_VALVE_ID,
    VALVE_HIGH_ID,
    VALVE_LOW_ID,
    llm_item,
    llm_recommendations,
    make_snapshot,
)

MAX_RECOMMENDATIONS = 5
MAX_REASON_LENGTH = 280
PATH = "/v1/insights/recommendations"
UseLlm = Callable[[FakeLlmClient | None], None]


def post(client: TestClient, snapshot: dict[str, Any]) -> dict[str, Any]:
    response = client.post(PATH, json={"snapshot": snapshot})
    assert response.status_code == HTTPStatus.OK, response.text
    body: dict[str, Any] = response.json()
    return body


def test_valid_llm_answer_is_marked_llm(client: TestClient, use_llm: UseLlm) -> None:
    fake = FakeLlmClient(llm_recommendations(llm_item("OPEN", VALVE_HIGH_ID)))
    use_llm(fake)
    body = post(client, make_snapshot())
    assert body["source"] == "LLM"
    assert body["model"] == "fake-llm-1"
    assert body["summary"] == "Resumen del modelo."
    assert body["recommendations"][0]["valve_id"] == VALVE_HIGH_ID
    assert len(fake.prompts) == 1


@pytest.mark.parametrize(
    "error",
    [
        LlmError("timeout"),
        LlmError("rate limited (429)"),
    ],
)
def test_llm_failure_falls_back_to_rules(
    client: TestClient, use_llm: UseLlm, error: Exception
) -> None:
    use_llm(FakeLlmClient(error=error))
    body = post(client, make_snapshot())
    assert body["source"] == "RULES"
    assert body["model"] == "rules-v1"
    assert body["recommendations"]


@pytest.mark.parametrize(
    "answer",
    [
        {"unexpected": True},
        {
            "summary": "x",
            "recommendations": [{"action": "EXPLODE", "reason": "x", "confidence": 1}],
        },
        {"summary": "x", "recommendations": [], "extra": 1},
        {
            "summary": "x",
            "recommendations": [llm_item("WAIT", None) | {"confidence": 7}],
        },
    ],
)
def test_invalid_llm_json_falls_back_to_rules(
    client: TestClient, use_llm: UseLlm, answer: dict[str, Any]
) -> None:
    use_llm(FakeLlmClient(answer))
    assert post(client, make_snapshot())["source"] == "RULES"


def test_no_llm_configured_uses_rules(client: TestClient, use_llm: UseLlm) -> None:
    use_llm(None)
    body = post(client, make_snapshot())
    assert body["source"] == "RULES"
    # Active schedule slot, healthy tank: open the Alto valve.
    assert [(r["action"], r["valve_id"]) for r in body["recommendations"]] == [
        ("OPEN", VALVE_HIGH_ID)
    ]


def test_reserve_floor_guard_removes_open_from_llm(
    client: TestClient, use_llm: UseLlm
) -> None:
    answer = llm_recommendations(
        llm_item("OPEN", VALVE_HIGH_ID),
        llm_item("CLOSE", VALVE_LOW_ID),
    )
    use_llm(FakeLlmClient(answer))
    body = post(client, make_snapshot(level_pct=25.0, floor=25.0))
    assert body["source"] == "LLM"
    assert [r["action"] for r in body["recommendations"]] == ["CLOSE"]


def test_llm_with_only_forbidden_open_falls_back_to_rules(
    client: TestClient, use_llm: UseLlm
) -> None:
    use_llm(FakeLlmClient(llm_recommendations(llm_item("OPEN", VALVE_HIGH_ID))))
    body = post(client, make_snapshot(level_pct=10.0))
    assert body["source"] == "RULES"
    assert all(r["action"] != "OPEN" for r in body["recommendations"])


def test_rules_never_open_at_or_below_floor(
    client: TestClient, use_llm: UseLlm
) -> None:
    use_llm(None)
    body = post(client, make_snapshot(level_pct=20.0))
    actions = {r["action"] for r in body["recommendations"]}
    assert "OPEN" not in actions
    assert ("CLOSE", VALVE_LOW_ID) in [
        (r["action"], r["valve_id"]) for r in body["recommendations"]
    ]


def test_rules_wait_when_forecast_would_cross_the_floor(
    client: TestClient, use_llm: UseLlm
) -> None:
    use_llm(None)
    snapshot = make_snapshot(level_pct=60.0)
    snapshot["forecast"][0]["p10"] = 0.5  # 20 % of 2.5 m
    body = post(client, snapshot)
    assert [r["action"] for r in body["recommendations"]] == ["WAIT"]


def test_unknown_valve_id_is_discarded(client: TestClient, use_llm: UseLlm) -> None:
    answer = llm_recommendations(
        llm_item("CLOSE", UNKNOWN_VALVE_ID),
        llm_item("CLOSE", "not-a-uuid"),
        llm_item("CLOSE", VALVE_LOW_ID),
    )
    use_llm(FakeLlmClient(answer))
    body = post(client, make_snapshot())
    assert [r["valve_id"] for r in body["recommendations"]] == [VALVE_LOW_ID]


def test_at_most_five_recommendations_and_reason_is_cut(
    client: TestClient, use_llm: UseLlm
) -> None:
    items = [llm_item("WAIT", None, reason="r" * 400) for _ in range(8)]
    use_llm(FakeLlmClient(llm_recommendations(*items)))
    body = post(client, make_snapshot())
    assert len(body["recommendations"]) == MAX_RECOMMENDATIONS
    assert all(len(r["reason"]) <= MAX_REASON_LENGTH for r in body["recommendations"])


def test_prompt_carries_the_snapshot(client: TestClient, use_llm: UseLlm) -> None:
    fake = FakeLlmClient(llm_recommendations(llm_item("WAIT", None)))
    use_llm(fake)
    post(client, make_snapshot())
    system, user = fake.prompts[0]
    assert "Nunca recomiendes OPEN" in system
    assert VALVE_HIGH_ID in user


def test_missing_token_is_401_with_standard_error(client: TestClient) -> None:
    response = client.post(
        PATH, json={"snapshot": make_snapshot()}, headers={"Authorization": ""}
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_extra_field_is_rejected_with_standard_error(client: TestClient) -> None:
    snapshot = make_snapshot()
    snapshot["surprise"] = 1
    response = client.post(PATH, json={"snapshot": snapshot})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"] == {"field": "surprise", "reason": "UNKNOWN_FIELD"}


def test_too_many_valves_is_rejected(client: TestClient) -> None:
    snapshot = make_snapshot()
    snapshot["valves"] = snapshot["valves"][:1] * 201
    response = client.post(PATH, json={"snapshot": snapshot})
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_naive_datetime_is_rejected(client: TestClient) -> None:
    snapshot = make_snapshot()
    snapshot["generated_at"] = "2026-11-07T10:00:00"
    assert (
        client.post(PATH, json={"snapshot": snapshot}).status_code
        == HTTPStatus.BAD_REQUEST
    )
