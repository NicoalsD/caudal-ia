from collections.abc import Generator
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from caudal_ia.config import MIN_SERVICE_TOKEN_BYTES, Settings, get_settings
from caudal_ia.main import app
from tests.conftest import TEST_SERVICE_TOKEN

FORECAST_PATH = "/v1/forecasts"
MODELS_PATH = "/v1/models"
HEALTH_PATH = "/v1/health"
PREVIOUS_TOKEN = "previous-service-token-with-at-least-32-bytes"
UNKNOWN_TOKEN = "unknown-service-token-with-at-least-32-bytes"
SERIES_ID = "0190f3a2-8888-7000-8000-000000000001"
SAMPLE_POINTS = 7
WWW_AUTHENTICATE = "WWW-Authenticate"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def forecast_payload() -> dict[str, Any]:
    return {
        "series_id": SERIES_ID,
        "timestamps": [
            f"2026-10-{day:02d}T18:00:00-05:00" for day in range(1, SAMPLE_POINTS + 1)
        ],
        "values": [2.0] * SAMPLE_POINTS,
        "prediction_length": 1,
        "quantile_levels": [0.1, 0.5, 0.9],
    }


@pytest.fixture
def anonymous_client() -> Generator[TestClient, None, None]:
    get_settings.cache_clear()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        get_settings.cache_clear()


def assert_unauthorized(response: Any) -> None:
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.headers[WWW_AUTHENTICATE] == "Bearer"
    error = response.json()["error"]
    assert error["code"] == "UNAUTHORIZED"
    assert error["details"] == {}
    assert TEST_SERVICE_TOKEN not in response.text


@pytest.mark.parametrize(
    "headers",
    [
        {},
        bearer(UNKNOWN_TOKEN),
        {"Authorization": f"Basic {TEST_SERVICE_TOKEN}"},
        {"Authorization": "Bearer"},
        bearer(TEST_SERVICE_TOKEN[:-1]),
    ],
    ids=["missing", "unknown", "wrong-scheme", "empty", "prefix"],
)
@pytest.mark.parametrize(
    "method, path", [("POST", FORECAST_PATH), ("GET", MODELS_PATH)]
)
def test_protected_routes_reject_missing_or_invalid_token(
    anonymous_client: TestClient,
    headers: dict[str, str],
    method: str,
    path: str,
) -> None:
    response = anonymous_client.request(
        method, path, headers=headers, json=forecast_payload()
    )

    assert_unauthorized(response)


def test_unauthorized_request_is_rejected_before_body_validation(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.post(FORECAST_PATH, json={"foo": "bar"})

    assert_unauthorized(response)


def test_health_does_not_require_token(anonymous_client: TestClient) -> None:
    response = anonymous_client.get(HEALTH_PATH)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


def test_current_token_is_accepted(anonymous_client: TestClient) -> None:
    response = anonymous_client.get(MODELS_PATH, headers=bearer(TEST_SERVICE_TOKEN))

    assert response.status_code == HTTPStatus.OK


def test_previous_token_is_accepted_only_during_rotation(
    anonymous_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IA_SERVICE_TOKEN_PREVIOUS", PREVIOUS_TOKEN)
    get_settings.cache_clear()

    during_rotation = anonymous_client.get(MODELS_PATH, headers=bearer(PREVIOUS_TOKEN))
    current_during_rotation = anonymous_client.get(
        MODELS_PATH, headers=bearer(TEST_SERVICE_TOKEN)
    )

    monkeypatch.delenv("IA_SERVICE_TOKEN_PREVIOUS")
    get_settings.cache_clear()

    after_rotation = anonymous_client.get(MODELS_PATH, headers=bearer(PREVIOUS_TOKEN))

    assert during_rotation.status_code == HTTPStatus.OK
    assert current_during_rotation.status_code == HTTPStatus.OK
    assert_unauthorized(after_rotation)


def test_service_does_not_start_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("IA_SERVICE_TOKEN")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("variable", ["IA_SERVICE_TOKEN", "IA_SERVICE_TOKEN_PREVIOUS"])
def test_tokens_shorter_than_minimum_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
) -> None:
    monkeypatch.setenv(variable, "x" * (MIN_SERVICE_TOKEN_BYTES - 1))

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_token_length_is_measured_in_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    two_byte_character = "ñ"
    monkeypatch.setenv(
        "IA_SERVICE_TOKEN", two_byte_character * (MIN_SERVICE_TOKEN_BYTES // 2)
    )

    assert len(Settings(_env_file=None).accepted_service_tokens()) == 1


def test_token_is_hidden_in_settings_representation() -> None:
    assert TEST_SERVICE_TOKEN not in repr(Settings(_env_file=None))
