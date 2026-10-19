import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

import caudal_ia.evaluation.__main__ as cli
from caudal_ia.config import Settings, get_settings
from caudal_ia.evaluation.report import VERDICT_DOES_NOT_HELP, VERDICT_INSUFFICIENT
from tests.fakes import DeterministicForecaster

FIRST_DAY = date(2026, 7, 1)
LONG_SERIES_DAYS = 40
SHORT_SERIES_DAYS = 20
HORIZON = "2"
MIN_CONTEXT = "5"
EXIT_OK = 0
EXIT_ERROR = 2
DEFAULT_MIN_CONTEXT = 7


def write_series(
    path: Path,
    days: int = LONG_SERIES_DAYS,
    **overrides: Any,
) -> Path:
    payload: dict[str, Any] = {
        "timestamps": [
            f"{(FIRST_DAY + timedelta(days=day)).isoformat()}T18:00:00-05:00"
            for day in range(days)
        ],
        "values": [3.0 - 0.01 * day for day in range(days)],
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def run(
    tmp_path: Path,
    *extra: str,
    series: Path | None = None,
    output_name: str = "informe.json",
) -> tuple[int, Path]:
    source = series or write_series(tmp_path / "serie.json")
    output = tmp_path / output_name
    code = cli.main(
        ["--input", str(source), "--output", str(output), *extra],
        forecaster_factory=lambda _settings: DeterministicForecaster(),
    )
    return code, output


def read_report(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def test_persistence_only_run_writes_a_report(tmp_path: Path) -> None:
    source = write_series(tmp_path / "serie.json")
    output = tmp_path / "informe.json"

    code = cli.main(
        [
            "--input",
            str(source),
            "--output",
            str(output),
            "--horizon",
            HORIZON,
            "--min-context",
            MIN_CONTEXT,
            "--persistence-only",
        ]
    )

    assert code == EXIT_OK
    report = read_report(output)
    assert report["model"]["name"] == "naive-persistence"
    assert report["parameters"]["horizon"] == int(HORIZON)
    assert report["parameters"]["min_context"] == int(MIN_CONTEXT)
    assert report["simulated_data"] is False
    assert [item["horizon"] for item in report["horizons"]] == [1, 2]


def test_injected_forecaster_is_the_model_under_test(tmp_path: Path) -> None:
    code, output = run(tmp_path, "--horizon", HORIZON, "--min-context", MIN_CONTEXT)

    assert code == EXIT_OK
    report = read_report(output)
    assert report["model"] == {"name": "fake/model", "version": "test"}
    assert report["baseline"] == {"name": "naive-persistence", "version": "1"}
    # The fake model and the persistence baseline share the median: no skill.
    assert all(item["skill"] == pytest.approx(0.0) for item in report["horizons"])
    assert report["verdict"] == VERDICT_DOES_NOT_HELP


def test_simulated_flag_is_written(tmp_path: Path) -> None:
    code, output = run(tmp_path, "--simulated")

    assert code == EXIT_OK
    assert read_report(output)["simulated_data"] is True


def test_default_min_context_is_forecast_min_points(tmp_path: Path) -> None:
    code, output = run(tmp_path)

    assert code == EXIT_OK
    assert read_report(output)["parameters"]["min_context"] == DEFAULT_MIN_CONTEXT
    assert read_report(output)["parameters"]["step"] == 1


def test_short_series_gives_insufficient_evidence(tmp_path: Path) -> None:
    short = write_series(tmp_path / "corta.json", days=SHORT_SERIES_DAYS)

    code, output = run(tmp_path, series=short, output_name="corta-informe.json")

    assert code == EXIT_OK
    assert read_report(output)["verdict"] == VERDICT_INSUFFICIENT


def test_help_runs_as_a_module() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "caudal_ia.evaluation", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == EXIT_OK
    assert "--persistence-only" in completed.stdout


@pytest.mark.parametrize(
    "payload",
    [
        {"timestamps": ["2026-07-01T18:00:00-05:00"], "values": [1.0, 2.0]},
        {"timestamps": [], "values": []},
        {"timestamps": ["2026-07-01T18:00:00-05:00"], "values": ["alto"]},
        {"timestamps": ["2026-07-01T18:00:00"], "values": [1.0]},
        {"timestamps": ["2026-07-01T18:00:00-05:00"]},
        ["no", "es", "objeto"],
    ],
    ids=[
        "length-mismatch",
        "empty",
        "text-value",
        "no-timezone",
        "missing-values",
        "not-an-object",
    ],
)
def test_invalid_series_is_rejected_without_writing(
    tmp_path: Path, payload: Any
) -> None:
    source = tmp_path / "mala.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    code, output = run(tmp_path, series=source)

    assert code == EXIT_ERROR
    assert not output.exists()


def test_non_finite_value_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "nan.json"
    source.write_text(
        '{"timestamps": ["2026-07-01T18:00:00-05:00"], "values": [NaN]}',
        encoding="utf-8",
    )

    code, _ = run(tmp_path, series=source)

    assert code == EXIT_ERROR


def test_missing_input_file_is_an_error(tmp_path: Path) -> None:
    code, output = run(tmp_path, series=tmp_path / "no-existe.json")

    assert code == EXIT_ERROR
    assert not output.exists()


def test_invalid_horizon_is_an_error(tmp_path: Path) -> None:
    code, output = run(tmp_path, "--horizon", "0")

    assert code == EXIT_ERROR
    assert not output.exists()


def test_missing_service_token_is_reported_in_spanish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def settings_without_token() -> Settings:
        monkeypatch.delenv("IA_SERVICE_TOKEN", raising=False)
        return Settings(_env_file=None)

    monkeypatch.setattr(cli, "get_settings", settings_without_token)
    source = write_series(tmp_path / "serie.json")

    code = cli.main(
        ["--input", str(source), "--output", str(tmp_path / "x.json")],
        forecaster_factory=lambda _settings: DeterministicForecaster(),
    )

    assert code == EXIT_ERROR
    assert "IA_SERVICE_TOKEN" in capsys.readouterr().err
    get_settings.cache_clear()


def test_required_arguments_are_enforced() -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["--input", "serie.json"])

    assert error.value.code == EXIT_ERROR
