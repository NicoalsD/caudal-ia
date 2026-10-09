import json
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any

from fastapi.testclient import TestClient

from caudal_ia.config import get_settings

FORECAST_PATH = "/v1/forecasts"
BOGOTA_OFFSET = timezone(timedelta(hours=-5))
FIRST_DAY = datetime(2026, 10, 1, 18, tzinfo=BOGOTA_OFFSET)
SERIES_ID = "0190f3a2-8888-7000-8000-000000000001"
VALID_PREDICTION_LENGTH = 1
OVER_MAXIMUM_PREDICTION_LENGTH = 31
VALID_QUANTILE_LEVELS = [0.1, 0.5, 0.9]
INVALID_QUANTILE_LEVELS = [0.1, 0.9]
NOT_FINITE_INDEX = 2
DUPLICATE_TIMESTAMP_INDEX = 1
ONE_POINT_OVER_MAXIMUM = 1


def build_payload(points: int) -> dict[str, Any]:
    timestamps = [
        (FIRST_DAY + timedelta(days=offset)).isoformat() for offset in range(points)
    ]
    return {
        "series_id": SERIES_ID,
        "timestamps": timestamps,
        "values": [2.0] * points,
        "prediction_length": VALID_PREDICTION_LENGTH,
        "quantile_levels": VALID_QUANTILE_LEVELS,
    }


def minimum_points() -> int:
    return get_settings().forecast_min_points


def test_prediction_length_above_technical_limit_returns_validation_error(
    client: TestClient,
) -> None:
    payload = build_payload(minimum_points())
    payload["prediction_length"] = OVER_MAXIMUM_PREDICTION_LENGTH

    response = client.post(FORECAST_PATH, json=payload)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"] == {
        "field": "prediction_length",
        "reason": "PREDICTION_LENGTH_OUT_OF_RANGE",
    }


def test_unsupported_quantile_levels_return_validation_error(
    client: TestClient,
) -> None:
    payload = build_payload(minimum_points())
    payload["quantile_levels"] = INVALID_QUANTILE_LEVELS

    response = client.post(FORECAST_PATH, json=payload)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"] == {
        "field": "quantile_levels",
        "reason": "QUANTILE_LEVELS_NOT_SUPPORTED",
    }


def test_non_increasing_timestamps_return_invalid_series(client: TestClient) -> None:
    payload = build_payload(minimum_points())
    payload["timestamps"][DUPLICATE_TIMESTAMP_INDEX] = payload["timestamps"][0]

    response = client.post(FORECAST_PATH, json=payload)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "INVALID_SERIES"
    assert response.json()["error"]["details"] == {
        "reason": "TIMESTAMPS_NOT_INCREASING",
        "index": DUPLICATE_TIMESTAMP_INDEX,
    }


def test_non_finite_value_returns_invalid_series(client: TestClient) -> None:
    payload = build_payload(minimum_points())
    payload["values"][NOT_FINITE_INDEX] = float("nan")

    # json.dumps keeps NaN as a token; httpx's json= argument refuses it.
    response = client.post(
        FORECAST_PATH,
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "INVALID_SERIES"
    assert response.json()["error"]["details"] == {
        "reason": "NOT_FINITE_VALUE",
        "index": NOT_FINITE_INDEX,
    }


def test_series_above_maximum_points_returns_invalid_series(
    client: TestClient,
) -> None:
    maximum = get_settings().max_series_points
    payload = build_payload(maximum + ONE_POINT_OVER_MAXIMUM)

    response = client.post(FORECAST_PATH, json=payload)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "INVALID_SERIES"
    assert response.json()["error"]["details"]["reason"] == "TOO_MANY_POINTS"
