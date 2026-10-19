from caudal_ia.domain import ForecastResult
from caudal_ia.schemas import ForecastPointResponse, ForecastResponse, ModelInfo


class ForecastResponseAdapter:
    """Convert domain forecast results to the HTTP response contract.

    @pattern P06 Adapter
    """

    def to_response(self, result: ForecastResult) -> ForecastResponse:
        return ForecastResponse(
            model=ModelInfo(
                name=result.model_name,
                version=result.model_version,
                notes=result.notes,
            ),
            generated_at=result.generated_at,
            frequency="D",
            points=[
                ForecastPointResponse(
                    timestamp=point.timestamp,
                    p10=point.p10,
                    p50=point.p50,
                    p90=point.p90,
                )
                for point in result.points
            ],
        )
