import json
import math
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from caudal_ia.config import Settings, get_settings
from caudal_ia.evaluation.backtest import ModelBacktest
from caudal_ia.evaluation.baseline import PersistenceForecaster
from caudal_ia.evaluation.report import (
    VERDICT_DOES_NOT_HELP,
    VERDICT_HELPS,
    VERDICT_INSUFFICIENT,
    BacktestReport,
    BacktestThresholds,
    HorizonReport,
    ModelIdentity,
    ReportContext,
    SideMetrics,
    build_report,
    decide_verdict,
)
from caudal_ia.evaluation.windows import BacktestParameters
from caudal_ia.forecasting.preprocessing import DailySeries
from tests.fakes import DeterministicForecaster

THRESHOLDS = BacktestThresholds(min_evaluations=30, coverage_min=0.7, coverage_max=0.9)
GOOD_SKILL = 0.2
GOOD_COVERAGE = 0.8
ENOUGH = 30
TOO_FEW = 29
SERIES_DAYS = 40
PARAMETERS = BacktestParameters(horizon=2, min_context=5, step=1)
FIRST_DAY = date(2026, 10, 1)


def side(coverage: float | None) -> SideMetrics:
    return SideMetrics(mae=1.0, wql=1.0, coverage=coverage, mean_width=1.0)


def horizon(
    number: int = 1,
    evaluated: int = ENOUGH,
    skill: float | None = GOOD_SKILL,
    coverage: float | None = GOOD_COVERAGE,
) -> HorizonReport:
    return HorizonReport(number, evaluated, side(coverage), side(None), skill)


@pytest.mark.parametrize(
    "horizons, expected",
    [
        ((horizon(1), horizon(2)), VERDICT_HELPS),
        ((horizon(1, evaluated=TOO_FEW),), VERDICT_INSUFFICIENT),
        ((), VERDICT_INSUFFICIENT),
        ((horizon(1, skill=0.0),), VERDICT_DOES_NOT_HELP),
        ((horizon(1, skill=None),), VERDICT_DOES_NOT_HELP),
        ((horizon(1), horizon(2, skill=-0.1)), VERDICT_DOES_NOT_HELP),
        ((horizon(1, coverage=0.95),), VERDICT_DOES_NOT_HELP),
        ((horizon(1, coverage=0.5),), VERDICT_DOES_NOT_HELP),
        ((horizon(1, coverage=None),), VERDICT_DOES_NOT_HELP),
    ],
    ids=[
        "helps",
        "too-few-evaluations",
        "no-horizons",
        "skill-zero",
        "skill-undefined",
        "one-horizon-negative",
        "coverage-too-high",
        "coverage-too-low",
        "coverage-undefined",
    ],
)
def test_verdict_follows_section_9_3(
    horizons: tuple[HorizonReport, ...], expected: str
) -> None:
    assert decide_verdict(horizons, THRESHOLDS) == expected


def test_coverage_bounds_are_inclusive() -> None:
    at_bounds = (
        horizon(1, coverage=THRESHOLDS.coverage_min),
        horizon(2, coverage=THRESHOLDS.coverage_max),
    )

    assert decide_verdict(at_bounds, THRESHOLDS) == VERDICT_HELPS


def test_thresholds_come_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKTEST_MIN_EVALUATIONS", "12")
    monkeypatch.setenv("BACKTEST_COVERAGE_MIN", "0.6")
    monkeypatch.setenv("BACKTEST_COVERAGE_MAX", "0.95")
    get_settings.cache_clear()
    try:
        thresholds = BacktestThresholds.from_settings(get_settings())
    finally:
        get_settings.cache_clear()

    assert thresholds == BacktestThresholds(12, 0.6, 0.95)


def test_default_thresholds_match_the_specification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "BACKTEST_MIN_EVALUATIONS",
        "BACKTEST_COVERAGE_MIN",
        "BACKTEST_COVERAGE_MAX",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings()

    assert BacktestThresholds.from_settings(settings) == BacktestThresholds(
        30, 0.7, 0.9
    )


def test_inverted_coverage_band_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKTEST_COVERAGE_MIN", "0.9")
    monkeypatch.setenv("BACKTEST_COVERAGE_MAX", "0.7")

    with pytest.raises(ValidationError):
        Settings()


def daily_series() -> DailySeries:
    days = tuple(FIRST_DAY + timedelta(days=offset) for offset in range(SERIES_DAYS))
    values = tuple(float(offset + 1) for offset in range(SERIES_DAYS))
    return DailySeries(days=days, values=values)


def context(simulated: bool) -> ReportContext:
    return ReportContext(
        model=ModelIdentity("fake/model", "test"),
        baseline=ModelIdentity("naive-persistence", "1"),
        thresholds=BacktestThresholds(1, 0.0, 1.0),
        simulated_data=simulated,
        resample_aggregation="last",
        series_timezone="America/Bogota",
    )


def test_report_is_exported_as_valid_json(tmp_path: Path) -> None:
    series = daily_series()
    model_result = ModelBacktest(PARAMETERS, DeterministicForecaster()).run(series)
    baseline_result = ModelBacktest(PARAMETERS, PersistenceForecaster()).run(series)
    report = build_report(model_result, baseline_result, context(simulated=True))
    output = tmp_path / "informe.json"

    report.write(output)

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["simulated_data"] is True
    assert data["model"] == {"name": "fake/model", "version": "test"}
    assert data["parameters"]["horizon"] == PARAMETERS.horizon
    assert data["parameters"]["series_timezone"] == "America/Bogota"
    assert [item["horizon"] for item in data["horizons"]] == [1, 2]
    assert data["verdict"] == VERDICT_DOES_NOT_HELP


def test_skill_is_zero_when_model_and_persistence_share_the_median() -> None:
    series = daily_series()
    model_result = ModelBacktest(PARAMETERS, DeterministicForecaster()).run(series)
    baseline_result = ModelBacktest(PARAMETERS, PersistenceForecaster()).run(series)

    report = build_report(model_result, baseline_result, context(simulated=False))

    for item in report.horizons:
        assert item.skill is not None
        assert math.isclose(item.skill, 0.0, abs_tol=1e-12)
    # The windows need a full horizon, so the last cutoffs are not evaluated.
    expected_windows = SERIES_DAYS - PARAMETERS.min_context - PARAMETERS.horizon + 1
    assert report.horizons[0].evaluated == expected_windows


def test_json_export_rejects_nan_instead_of_writing_invalid_json() -> None:
    broken = HorizonReport(1, ENOUGH, side(math.nan), side(None), None)
    report = BacktestReport(
        context=context(simulated=False),
        parameters=PARAMETERS,
        horizons=(broken,),
        verdict=VERDICT_INSUFFICIENT,
    )

    with pytest.raises(ValueError, match="not JSON compliant"):
        report.to_json()
