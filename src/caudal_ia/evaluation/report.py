import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from caudal_ia.config import Settings
from caudal_ia.evaluation.backtest import BacktestResult
from caudal_ia.evaluation.baseline import skill
from caudal_ia.evaluation.metrics import HorizonMetrics, horizon_metrics
from caudal_ia.evaluation.windows import BacktestParameters

VERDICT_INSUFFICIENT = "insufficient_evidence"
VERDICT_HELPS = "helps"
VERDICT_DOES_NOT_HELP = "does_not_help"
JSON_INDENT = 2


@dataclass(frozen=True)
class ModelIdentity:
    name: str
    version: str


@dataclass(frozen=True)
class BacktestThresholds:
    """Criteria of section 9.3 of the module specification."""

    min_evaluations: int
    coverage_min: float
    coverage_max: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "BacktestThresholds":
        return cls(
            min_evaluations=settings.backtest_min_evaluations,
            coverage_min=settings.backtest_coverage_min,
            coverage_max=settings.backtest_coverage_max,
        )


@dataclass(frozen=True)
class ReportContext:
    """Everything the report states besides the two backtest results."""

    model: ModelIdentity
    baseline: ModelIdentity
    thresholds: BacktestThresholds
    simulated_data: bool
    resample_aggregation: str
    series_timezone: str


@dataclass(frozen=True)
class SideMetrics:
    """Metrics of one forecaster (the model or the persistence baseline)."""

    mae: float | None
    wql: float | None
    coverage: float | None
    mean_width: float | None


@dataclass(frozen=True)
class HorizonReport:
    horizon: int
    evaluated: int
    model: SideMetrics
    persistence: SideMetrics
    skill: float | None


@dataclass(frozen=True)
class BacktestReport:
    context: ReportContext
    parameters: BacktestParameters
    horizons: tuple[HorizonReport, ...]
    verdict: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": asdict(self.context.model),
            "baseline": asdict(self.context.baseline),
            "parameters": {
                **asdict(self.parameters),
                "resample_aggregation": self.context.resample_aggregation,
                "series_timezone": self.context.series_timezone,
            },
            "thresholds": asdict(self.context.thresholds),
            "simulated_data": self.context.simulated_data,
            "horizons": [asdict(horizon) for horizon in self.horizons],
            "verdict": self.verdict,
        }

    def to_json(self) -> str:
        # allow_nan=False: a NaN metric must fail here, not produce invalid JSON.
        return json.dumps(
            self.to_dict(),
            indent=JSON_INDENT,
            ensure_ascii=False,
            allow_nan=False,
        )

    def write(self, path: Path) -> None:
        path.write_text(self.to_json() + "\n", encoding="utf-8")


def side_metrics(metrics: HorizonMetrics) -> SideMetrics:
    return SideMetrics(
        mae=metrics.mae,
        wql=metrics.wql,
        coverage=metrics.coverage,
        mean_width=metrics.mean_width,
    )


def build_horizon_reports(
    model_result: BacktestResult,
    baseline_result: BacktestResult,
) -> tuple[HorizonReport, ...]:
    """Compare model and persistence horizon by horizon over the same windows."""
    model_by_horizon = horizon_metrics(model_result)
    baseline_by_horizon = horizon_metrics(baseline_result)
    horizons: list[HorizonReport] = []
    for model, baseline in zip(model_by_horizon, baseline_by_horizon, strict=True):
        horizons.append(
            HorizonReport(
                horizon=model.horizon,
                evaluated=model.evaluated,
                model=side_metrics(model),
                persistence=side_metrics(baseline),
                skill=skill(model.mae, baseline.mae),
            )
        )
    return tuple(horizons)


def decide_verdict(
    horizons: tuple[HorizonReport, ...],
    thresholds: BacktestThresholds,
) -> str:
    """Apply section 9.3: enough evidence, skill above zero and calibrated coverage.

    Every horizon must have at least ``min_evaluations`` forecasts, a positive
    skill and a coverage inside ``[coverage_min, coverage_max]``.
    """
    if not horizons or any(
        horizon.evaluated < thresholds.min_evaluations for horizon in horizons
    ):
        return VERDICT_INSUFFICIENT
    helps = all(
        horizon.skill is not None
        and horizon.skill > 0
        and horizon.model.coverage is not None
        and thresholds.coverage_min <= horizon.model.coverage <= thresholds.coverage_max
        for horizon in horizons
    )
    return VERDICT_HELPS if helps else VERDICT_DOES_NOT_HELP


def build_report(
    model_result: BacktestResult,
    baseline_result: BacktestResult,
    context: ReportContext,
) -> BacktestReport:
    horizons = build_horizon_reports(model_result, baseline_result)
    return BacktestReport(
        context=context,
        parameters=model_result.parameters,
        horizons=horizons,
        verdict=decide_verdict(horizons, context.thresholds),
    )
