import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import ValidationError

from caudal_ia.config import Settings, get_settings
from caudal_ia.evaluation.backtest import ModelBacktest
from caudal_ia.evaluation.baseline import PersistenceForecaster
from caudal_ia.evaluation.report import (
    BacktestThresholds,
    ModelIdentity,
    ReportContext,
    build_report,
)
from caudal_ia.evaluation.windows import BacktestParameters
from caudal_ia.forecasting.creator import ChronosForecasterCreator
from caudal_ia.forecasting.forecaster import Forecaster
from caudal_ia.forecasting.preprocessing import (
    DAILY_AGGREGATIONS,
    DailySeries,
    prepare_daily_series,
)
from caudal_ia.model_registry import resolve_active_model
from caudal_ia.series_validation import SeriesValidationError, validate_series

DEFAULT_HORIZON = 3
DEFAULT_STEP = 1
EXIT_OK = 0
EXIT_ERROR = 2

ForecasterFactory = Callable[[Settings], Forecaster]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m caudal_ia.evaluation",
        description=(
            "Backtest offline del modelo frente a la estimación simple. Lee una "
            "serie en JSON con 'timestamps' y 'values' y escribe un informe JSON."
        ),
    )
    parser.add_argument("--input", type=Path, required=True, help="Serie en JSON.")
    parser.add_argument("--output", type=Path, required=True, help="Informe JSON.")
    parser.add_argument(
        "--horizon",
        type=int,
        default=DEFAULT_HORIZON,
        help="Días a pronosticar en cada ventana (por defecto 3).",
    )
    parser.add_argument(
        "--min-context",
        type=int,
        default=None,
        help="Días mínimos de contexto (por defecto FORECAST_MIN_POINTS).",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=DEFAULT_STEP,
        help="Días entre dos cortes consecutivos (por defecto 1).",
    )
    parser.add_argument(
        "--simulated",
        action="store_true",
        help="Marca el informe como de datos simulados.",
    )
    parser.add_argument(
        "--persistence-only",
        action="store_true",
        help="Usa la estimación simple como modelo, sin cargar Chronos.",
    )
    return parser


def read_series_file(path: Path, settings: Settings) -> tuple[list[str], list[float]]:
    """Read ``timestamps`` and ``values`` and apply the rules of the contract."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("El archivo debe contener un objeto JSON.")
    timestamps = payload.get("timestamps")
    values = payload.get("values")
    if not isinstance(timestamps, list) or not isinstance(values, list):
        raise ValueError("El archivo necesita las listas 'timestamps' y 'values'.")
    if not timestamps:
        raise ValueError("La serie está vacía.")
    if not all(isinstance(item, str) for item in timestamps) or not all(
        isinstance(item, int | float) and not isinstance(item, bool) for item in values
    ):
        raise ValueError("'timestamps' debe ser texto y 'values' debe ser numérico.")
    numbers = [float(item) for item in values]
    validate_series(timestamps, numbers, settings)
    return timestamps, numbers


def chronos_forecaster(settings: Settings) -> Forecaster:
    """Load the active Chronos model, as the service does at startup."""
    spec = resolve_active_model(settings)
    return ChronosForecasterCreator().create(spec, settings)


def to_daily_series(
    timestamps: list[str],
    values: list[float],
    settings: Settings,
) -> DailySeries:
    return prepare_daily_series(
        timestamps,
        values,
        settings.zone,
        DAILY_AGGREGATIONS[settings.resample_aggregation],
    )


def main(
    argv: Sequence[str] | None = None,
    forecaster_factory: ForecasterFactory | None = None,
) -> int:
    """Run the backtest and write the report. ``forecaster_factory`` is for tests."""
    args = build_parser().parse_args(argv)
    try:
        settings = get_settings()
    except ValidationError:
        print(
            "Error: la configuración no es válida. Revisa IA_SERVICE_TOKEN "
            "en el entorno o en .env.",
            file=sys.stderr,
        )
        return EXIT_ERROR
    try:
        timestamps, values = read_series_file(args.input, settings)
        series = to_daily_series(timestamps, values, settings)
        parameters = BacktestParameters(
            horizon=args.horizon,
            min_context=(
                args.min_context
                if args.min_context is not None
                else settings.forecast_min_points
            ),
            step=args.step,
        )
        if args.persistence_only:
            model_forecaster: Forecaster = PersistenceForecaster()
        else:
            factory = forecaster_factory or chronos_forecaster
            model_forecaster = factory(settings)
        baseline = PersistenceForecaster()
        model_result = ModelBacktest(parameters, model_forecaster).run(series)
        baseline_result = ModelBacktest(parameters, baseline).run(series)
        report = build_report(
            model_result,
            baseline_result,
            ReportContext(
                model=ModelIdentity(model_forecaster.name, model_forecaster.version),
                baseline=ModelIdentity(baseline.name, baseline.version),
                thresholds=BacktestThresholds.from_settings(settings),
                simulated_data=args.simulated,
                resample_aggregation=settings.resample_aggregation,
                series_timezone=settings.series_timezone,
            ),
        )
        report.write(args.output)
    except (OSError, ValueError, SeriesValidationError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return EXIT_ERROR
    print(f"Veredicto: {report.verdict}. Informe: {args.output}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
