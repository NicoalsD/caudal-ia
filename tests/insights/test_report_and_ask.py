from collections.abc import Callable
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient

from caudal_ia.insights.llm import LlmError
from tests.fakes import FakeLlmClient
from tests.insights.helpers import make_snapshot

REPORT_PATH = "/v1/insights/report"
ASK_PATH = "/v1/insights/ask"
UseLlm = Callable[[FakeLlmClient | None], None]

REPORT_LLM = {
    "title": "Informe de octubre",
    "summary": "Todo estable.",
    "findings": ["Consumo estable."],
    "recommendations": ["Mantener los turnos."],
}


def report_body() -> dict[str, Any]:
    return {
        "aqueduct_name": "Vereda demo",
        "from": "2026-10-01T00:00:00-05:00",
        "to": "2026-10-31T23:59:59-05:00",
        "aggregates": {"readings": 120, "avg_level_pct": 61.5, "nested": {"a": 1}},
    }


def test_report_with_llm(client: TestClient, use_llm: UseLlm) -> None:
    fake = FakeLlmClient(REPORT_LLM)
    use_llm(fake)
    response = client.post(REPORT_PATH, json=report_body())
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["source"] == "LLM"
    assert body["title"] == "Informe de octubre"
    assert "# Informe de octubre" in body["markdown"]
    assert "- Consumo estable." in body["markdown"]
    assert "avg_level_pct" in fake.prompts[0][1]


@pytest.mark.parametrize(
    "llm",
    [None, FakeLlmClient(error=LlmError("429")), FakeLlmClient({"title": 1})],
)
def test_report_falls_back_to_template(
    client: TestClient, use_llm: UseLlm, llm: FakeLlmClient | None
) -> None:
    use_llm(llm)
    body = client.post(REPORT_PATH, json=report_body()).json()
    assert body["source"] == "RULES"
    assert body["model"] == "rules-v1"
    assert "readings: 120" in body["findings"]
    assert "nested" not in " ".join(body["findings"])


def test_report_rejects_oversized_aggregates(client: TestClient) -> None:
    payload = report_body()
    payload["aggregates"] = {"blob": "x" * 33_000}
    response = client.post(REPORT_PATH, json=payload)
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_report_rejects_reversed_period_and_extra_field(client: TestClient) -> None:
    reversed_period = report_body() | {"from": "2026-11-01T00:00:00-05:00"}
    assert (
        client.post(REPORT_PATH, json=reversed_period).status_code
        == HTTPStatus.BAD_REQUEST
    )
    extra = report_body() | {"surprise": 1}
    assert client.post(REPORT_PATH, json=extra).status_code == HTTPStatus.BAD_REQUEST


def test_ask_with_llm(client: TestClient, use_llm: UseLlm) -> None:
    fake = FakeLlmClient({"answer": "El tanque está al 72 %."})
    use_llm(fake)
    response = client.post(
        ASK_PATH, json={"question": "¿Cómo va el tanque?", "snapshot": make_snapshot()}
    )
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert (body["source"], body["answer"]) == ("LLM", "El tanque está al 72 %.")
    assert "¿Cómo va el tanque?" in fake.prompts[0][1]


@pytest.mark.parametrize(
    "llm",
    [None, FakeLlmClient(error=LlmError("timeout")), FakeLlmClient({"answer": ""})],
)
def test_ask_falls_back_to_state_summary(
    client: TestClient, use_llm: UseLlm, llm: FakeLlmClient | None
) -> None:
    use_llm(llm)
    body = client.post(
        ASK_PATH, json={"question": "¿Hay agua?", "snapshot": make_snapshot()}
    ).json()
    assert body["source"] == "RULES"
    assert "72 %" in body["answer"]


def test_ask_validates_question_and_auth(client: TestClient) -> None:
    long_question = {"question": "x" * 501, "snapshot": make_snapshot()}
    assert (
        client.post(ASK_PATH, json=long_question).status_code == HTTPStatus.BAD_REQUEST
    )
    extra = {"question": "hola", "snapshot": make_snapshot(), "x": 1}
    assert client.post(ASK_PATH, json=extra).status_code == HTTPStatus.BAD_REQUEST
    anonymous = client.post(
        ASK_PATH,
        json={"question": "hola", "snapshot": make_snapshot()},
        headers={"Authorization": ""},
    )
    assert anonymous.status_code == HTTPStatus.UNAUTHORIZED
    assert (
        client.post(
            REPORT_PATH, json=report_body(), headers={"Authorization": ""}
        ).status_code
        == HTTPStatus.UNAUTHORIZED
    )
