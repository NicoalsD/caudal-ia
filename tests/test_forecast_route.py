from collections.abc import Iterator
from datetime import date, datetime, timedelta
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient

from caudal_ia.config import get_settings
from caudal_ia.forecasting.forecaster import ForecasterOutputError, QuantileForecast
from caudal_ia.main import app
from caudal_ia.model_registry import ModelRegistry
from tests.conftest import AUTHORIZATION_HEADERS

FORECAST_PATH = "/v1/forecasts"
SERIES_ID = "0190f3a2-8888-7000-8000-000000000001"
LOAD_TIMEOUT_SECONDS = 5.0
CONTRACT_EXAMPLE_VALUES = [3.10, 3.02, 2.90, 2.75, 2.60, 2.35, 2.10]
MAXIMUM_PREDICTION_LENGTH = 30


def contract_example(prediction_length: int = 1) -> dict[str, Any]:
    """Request of section 3.1 of the backend-IA contract (CT-01)."""
    return {
        "series_id": SERIES_ID,
        "timestamps": [f"2026-10-{day:02d}T18:00:00-05:00" for day in range(2, 9)],
        "values": CONTRACT_EXAMPLE_VALUES,
        "prediction_length": prediction_length,
        "quantile_levels": [0.1, 0.5, 0.9],
    }


@pytest.fixture
def ready_client(client: TestClient) -> TestClient:
    assert app.state.readiness.wait(LOAD_TIMEOUT_SECONDS)
    return client


def assert_contract_points(body: dict[str, Any], first_day: date, count: int) -> None:
    points = body["points"]
    assert len(points) == count
    for step, point in enumerate(points):
        timestamp = datetime.fromisoformat(point["timestamp"])
        assert timestamp.date() == first_day + timedelta(days=step)
        assert timestamp.utcoffset() == timedelta(hours=-5)
        assert (timestamp.hour, timestamp.minute) == (0, 0)
        assert point["p10"] <= point["p50"] <= point["p90"]


def test_contract_example_returns_one_point(ready_client: TestClient) -> None:
    response = ready_client.post(FORECAST_PATH, json=contract_example())

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["frequency"] == "D"
    assert body["model"]["name"] == get_settings().chronos_model_id
    assert body["model"]["version"].endswith("+last")
    assert "notes" not in body["model"]
    assert datetime.fromisoformat(body["generated_at"]).tzinfo is not None
    assert_contract_points(body, date(2026, 10, 9), 1)


def test_maximum_horizon_returns_consecutive_days(ready_client: TestClient) -> None:
    response = ready_client.post(
        FORECAST_PATH, json=contract_example(MAXIMUM_PREDICTION_LENGTH)
    )

    assert response.status_code == HTTPStatus.OK
    assert_contract_points(
        response.json(), date(2026, 10, 9), MAXIMUM_PREDICTION_LENGTH
    )


def test_forecast_starts_the_local_day_after_a_utc_reading(
    ready_client: TestClient,
) -> None:
    payload = contract_example()
    # 03:00 UTC on October 9 is still October 8 in Bogota.
    payload["timestamps"][-1] = "2026-10-09T03:00:00Z"

    response = ready_client.post(FORECAST_PATH, json=payload)

    assert response.status_code == HTTPStatus.OK
    assert_contract_points(response.json(), date(2026, 10, 9), 1)


def test_gaps_are_reported_in_model_notes(ready_client: TestClient) -> None:
    payload = contract_example()
    payload["timestamps"] = [
        f"2026-10-{day:02d}T18:00:00-05:00" for day in (1, 2, 3, 5, 6, 7, 9)
    ]

    response = ready_client.post(FORECAST_PATH, json=payload)

    assert response.status_code == HTTPStatus.OK
    assert response.json()["model"]["notes"].endswith(": 2.")


class BrokenForecaster:
    name = "broken"
    version = "1"

    def predict_quantiles(self, *args: object) -> QuantileForecast:
        raise ForecasterOutputError("broken output")


@pytest.fixture
def broken_model(ready_client: TestClient) -> Iterator[None]:
    registry = ModelRegistry.get_instance()
    model_name = app.state.readiness.model_name
    previous = registry.get_forecaster(model_name)
    registry._forecasters[model_name] = BrokenForecaster()  # type: ignore[assignment]
    try:
        yield
    finally:
        registry._forecasters[model_name] = previous


def test_model_failure_returns_internal_error_without_details(
    broken_model: None,
) -> None:
    with TestClient(
        app, headers=AUTHORIZATION_HEADERS, raise_server_exceptions=False
    ) as server_client:
        response = server_client.post(FORECAST_PATH, json=contract_example())

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert error["details"] == {}
    assert "broken output" not in response.text
