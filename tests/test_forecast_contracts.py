from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from caudal_ia.adapters import ForecastResponseAdapter
from caudal_ia.domain import ForecastPoint, ForecastResult
from caudal_ia.schemas import (
    ForecastPointResponse,
    ForecastRequest,
    ForecastResponse,
    ModelInfo,
)

EXPECTED_LAST_VALUE = 2.10


def test_forecast_request_accepts_contract_example() -> None:
    request = ForecastRequest.model_validate(
        {
            "series_id": "0190f3a2-8888-7000-8000-000000000001",
            "timestamps": [
                "2026-10-02T18:00:00-05:00",
                "2026-10-03T18:00:00-05:00",
                "2026-10-04T18:00:00-05:00",
                "2026-10-05T18:00:00-05:00",
                "2026-10-06T18:00:00-05:00",
                "2026-10-07T18:00:00-05:00",
                "2026-10-08T18:00:00-05:00",
            ],
            "values": [3.10, 3.02, 2.90, 2.75, 2.60, 2.35, 2.10],
            "prediction_length": 1,
            "quantile_levels": [0.1, 0.5, 0.9],
        }
    )

    assert str(request.series_id) == "0190f3a2-8888-7000-8000-000000000001"
    assert request.timestamps[-1] == "2026-10-08T18:00:00-05:00"
    assert request.values[-1] == EXPECTED_LAST_VALUE


def test_forecast_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ForecastRequest.model_validate(
            {
                "series_id": "0190f3a2-8888-7000-8000-000000000001",
                "timestamps": ["not parsed at this stage"],
                "values": [1.0],
                "prediction_length": 1,
                "quantile_levels": [0.1, 0.5, 0.9],
                "unexpected": True,
            }
        )


def test_forecast_request_rejects_non_uuid_series_id() -> None:
    with pytest.raises(ValidationError, match="Input should be a valid UUID"):
        ForecastRequest.model_validate(
            {
                "series_id": "tank-1",
                "timestamps": ["2026-10-08T18:00:00-05:00"],
                "values": [2.1],
                "prediction_length": 1,
                "quantile_levels": [0.1, 0.5, 0.9],
            }
        )


def test_forecast_response_adapter_maps_domain_result() -> None:
    generated_at = datetime(2026, 10, 9, 9, 30, tzinfo=UTC)
    timestamp = datetime.fromisoformat("2026-10-09T00:00:00-05:00")
    result = ForecastResult(
        model_name="autogluon/chronos-2-small",
        model_version="2.0.0",
        generated_at=generated_at,
        notes="Pronóstico diario.",
        points=(ForecastPoint(timestamp, 1.8, 2.1, 2.4),),
    )

    response = ForecastResponseAdapter().to_response(result)

    assert response == ForecastResponse(
        model=ModelInfo(
            name="autogluon/chronos-2-small",
            version="2.0.0",
            notes="Pronóstico diario.",
        ),
        generated_at=generated_at,
        frequency="D",
        points=[
            ForecastPointResponse(
                timestamp=timestamp,
                p10=1.8,
                p50=2.1,
                p90=2.4,
            )
        ],
    )
