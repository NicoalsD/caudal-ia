from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from caudal_ia.config import get_settings
from caudal_ia.main import app
from caudal_ia.readiness import ModelReadiness

FORECAST_PATH = "/v1/forecasts"
VALID_PREDICTION_LENGTH = 1
INVALID_PREDICTION_LENGTH = 0
VALID_QUANTILE_LEVELS = [0.1, 0.5, 0.9]
SAMPLE_BODY_LIMIT_BYTES = 10
RETRY_AFTER_HEADER = "Retry-After"
RETRY_AFTER_VALUE = "30"
SERIES_ID = "0190f3a2-8888-7000-8000-000000000001"


def build_payload(points: int) -> dict[str, Any]:
    timestamps = [f"2026-10-{day:02d}T18:00:00-05:00" for day in range(1, points + 1)]
    return {
        "series_id": SERIES_ID,
        "timestamps": timestamps,
        "values": [2.0] * points,
        "prediction_length": VALID_PREDICTION_LENGTH,
        "quantile_levels": VALID_QUANTILE_LEVELS,
    }


def assert_error_envelope(response_body: dict[str, Any], code: str) -> dict[str, Any]:
    error: dict[str, Any] = response_body["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert error["message"]
    assert isinstance(error["request_id"], str)
    assert error["request_id"]
    details: dict[str, Any] = error["details"]
    return details


def test_unknown_field_returns_validation_error(client: TestClient) -> None:
    payload = build_payload(get_settings().forecast_min_points)
    payload["unexpected"] = True

    response = client.post(FORECAST_PATH, json=payload)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    details = assert_error_envelope(response.json(), "VALIDATION_ERROR")
    assert details["reason"] == "UNKNOWN_FIELD"


def test_prediction_length_out_of_range_returns_validation_error(
    client: TestClient,
) -> None:
    payload = build_payload(get_settings().forecast_min_points)
    payload["prediction_length"] = INVALID_PREDICTION_LENGTH

    response = client.post(FORECAST_PATH, json=payload)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    details = assert_error_envelope(response.json(), "VALIDATION_ERROR")
    assert details == {
        "field": "prediction_length",
        "reason": "PREDICTION_LENGTH_OUT_OF_RANGE",
    }


def test_length_mismatch_returns_invalid_series(client: TestClient) -> None:
    payload = build_payload(get_settings().forecast_min_points)
    payload["values"] = payload["values"][:-1]

    response = client.post(FORECAST_PATH, json=payload)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    details = assert_error_envelope(response.json(), "INVALID_SERIES")
    assert details["reason"] == "LENGTH_MISMATCH"
    assert details["index"] is None


def test_insufficient_history_returns_422(client: TestClient) -> None:
    minimum = get_settings().forecast_min_points
    received = minimum - 1
    payload = build_payload(received)

    response = client.post(FORECAST_PATH, json=payload)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    details = assert_error_envelope(response.json(), "INSUFFICIENT_HISTORY")
    assert details == {"received": received, "minimum": minimum}


def test_oversized_body_returns_payload_too_large(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    try:
        with monkeypatch.context() as environment:
            environment.setenv("MAX_BODY_BYTES", str(SAMPLE_BODY_LIMIT_BYTES))
            get_settings.cache_clear()

            response = client.post(
                FORECAST_PATH, json=build_payload(get_settings().forecast_min_points)
            )

        assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
        details = assert_error_envelope(response.json(), "PAYLOAD_TOO_LARGE")
        assert details == {"limit_bytes": SAMPLE_BODY_LIMIT_BYTES}
    finally:
        get_settings.cache_clear()


@pytest.fixture
def not_loaded_readiness() -> object:
    previous_readiness = app.state.readiness
    app.state.readiness = ModelReadiness(get_settings().chronos_model_id)
    try:
        yield app.state.readiness
    finally:
        app.state.readiness = previous_readiness


def test_valid_request_returns_model_not_ready_when_model_is_not_loaded(
    client: TestClient, not_loaded_readiness: ModelReadiness
) -> None:
    payload = build_payload(get_settings().forecast_min_points)

    response = client.post(FORECAST_PATH, json=payload)

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.headers[RETRY_AFTER_HEADER] == RETRY_AFTER_VALUE
    details = assert_error_envelope(response.json(), "MODEL_NOT_READY")
    assert details == {"model_name": get_settings().chronos_model_id}


def test_readings_of_the_same_day_count_as_one_day(client: TestClient) -> None:
    minimum = get_settings().forecast_min_points
    payload = build_payload(minimum)
    payload["timestamps"] = [
        f"2026-10-01T{hour:02d}:00:00-05:00" for hour in range(minimum)
    ]

    response = client.post(FORECAST_PATH, json=payload)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    details = assert_error_envelope(response.json(), "INSUFFICIENT_HISTORY")
    assert details == {"received": 1, "minimum": minimum}


def test_insufficient_history_is_reported_while_the_model_loads(
    client: TestClient, not_loaded_readiness: ModelReadiness
) -> None:
    received = get_settings().forecast_min_points - 1

    response = client.post(FORECAST_PATH, json=build_payload(received))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert_error_envelope(response.json(), "INSUFFICIENT_HISTORY")
