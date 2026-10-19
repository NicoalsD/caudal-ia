"""Measure memory, load time and latency of the Chronos model on this machine.

Follows section 12.1 of Modulo-IA: RSS after loading the model, peak RSS with a
2.000-point series and prediction_length 30, load time, and latency for the
typical case (60 points, horizon 3) and the maximum case. Prints a JSON report
and exits with code 1 when the peak RSS is above the limit.

The model is loaded through ``ChronosForecasterCreator.create_forecaster`` (the
bare adapter, without the caching decorator) so repeated timing calls are not
answered from the cache.

Peak RSS comes from ``resource.getrusage`` and is the process peak since start,
so it covers model loading and both forecasts (Linux reports KiB).

Usage:
    uv run python scripts/measure_memory.py
    uv run python scripts/measure_memory.py --max-rss-mb 1500 --repetitions 3
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import resource
import secrets
import statistics
import sys
import time
from datetime import UTC, datetime

import torch
from pydantic import SecretStr

from caudal_ia.config import (
    DEFAULT_CHRONOS_MODEL_ID,
    DEFAULT_MAX_PREDICTION_LENGTH,
    DEFAULT_MAX_SERIES_POINTS,
    MIN_SERVICE_TOKEN_BYTES,
    Settings,
)
from caudal_ia.forecasting.creator import ChronosForecasterCreator
from caudal_ia.forecasting.forecaster import Forecaster
from caudal_ia.model_catalog import ModelSpec
from caudal_ia.model_registry import ModelRegistry

MEMORY_LIMIT_ENV = "MEMORY_LIMIT_MB"
# Indicative only: the real limit depends on the hosting plan (see deployment.md).
DEFAULT_MEMORY_LIMIT_MB = 2048
DEFAULT_REPETITIONS = 5
TYPICAL_CONTEXT_POINTS = 60
TYPICAL_PREDICTION_LENGTH = 3
MAXIMUM_CONTEXT_POINTS = DEFAULT_MAX_SERIES_POINTS
MAXIMUM_PREDICTION_LENGTH = DEFAULT_MAX_PREDICTION_LENGTH
KIB_PER_MB = 1024
MS_PER_SECOND = 1000
DECIMALS = 1
SERIES_BASE = 50.0
SERIES_AMPLITUDE = 10.0
SERIES_STEP = 0.1
PROC_STATUS = "/proc/self/status"
PROC_CPUINFO = "/proc/cpuinfo"
RSS_KEY = "VmRSS:"
CPU_MODEL_KEY = "model name"
SUPPORTED_PLATFORM = "linux"
UNSUPPORTED_PLATFORM_CODE = 2


def synthetic_series(points: int) -> list[float]:
    """Return a deterministic, smooth series of ``points`` values."""
    return [
        SERIES_BASE + SERIES_AMPLITUDE * math.sin(index * SERIES_STEP)
        for index in range(points)
    ]


def read_proc_value(path: str, key: str) -> str | None:
    """Return the text after ``key`` in a /proc file, or None if absent."""
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith(key):
                    return line[len(key) :].lstrip(" \t:").strip()
    except OSError:
        return None
    return None


def current_rss_mb() -> float | None:
    """Return the resident memory of this process right now, in MB."""
    value = read_proc_value(PROC_STATUS, RSS_KEY)
    if value is None:
        return None
    kib = int(value.split()[0])
    return round(kib / KIB_PER_MB, DECIMALS)


def peak_rss_mb() -> float:
    """Return the process peak resident memory since start, in MB."""
    kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(kib / KIB_PER_MB, DECIMALS)


def cpu_model() -> str | None:
    return read_proc_value(PROC_CPUINFO, CPU_MODEL_KEY)


def median_latency_ms(
    forecaster: Forecaster,
    spec: ModelSpec,
    context_points: int,
    prediction_length: int,
    repetitions: int,
) -> float:
    """Return the median latency of one forecast, after one warm-up call."""
    context = synthetic_series(context_points)
    levels = list(spec.quantile_levels)
    forecaster.predict_quantiles(context, prediction_length, levels)
    samples: list[float] = []
    for _ in range(repetitions):
        start = time.perf_counter()
        forecaster.predict_quantiles(context, prediction_length, levels)
        samples.append((time.perf_counter() - start) * MS_PER_SECOND)
    return round(statistics.median(samples), DECIMALS)


def measure_case(
    forecaster: Forecaster,
    spec: ModelSpec,
    context_points: int,
    prediction_length: int,
    repetitions: int,
) -> dict[str, float | int]:
    return {
        "context_points": context_points,
        "prediction_length": prediction_length,
        "latency_ms_median": median_latency_ms(
            forecaster, spec, context_points, prediction_length, repetitions
        ),
        "repetitions": repetitions,
    }


def build_settings(model_id: str) -> Settings:
    """Settings for the measurement; the throwaway token is never printed or used."""
    return Settings(
        ia_service_token=SecretStr(secrets.token_urlsafe(MIN_SERVICE_TOKEN_BYTES)),
        chronos_model_id=model_id,
    )


def default_memory_limit_mb() -> float:
    return float(os.environ.get(MEMORY_LIMIT_ENV, DEFAULT_MEMORY_LIMIT_MB))


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mide memoria y latencia del modelo Chronos (Modulo-IA 12.1)."
    )
    parser.add_argument("--model-id", default=DEFAULT_CHRONOS_MODEL_ID)
    parser.add_argument(
        "--max-rss-mb",
        type=float,
        default=default_memory_limit_mb(),
        help=f"Límite de memoria pico en MB (por defecto ${MEMORY_LIMIT_ENV}).",
    )
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if sys.platform != SUPPORTED_PLATFORM:
        print("Este script solo se ejecuta en Linux (usa ru_maxrss en KiB).")
        return UNSUPPORTED_PLATFORM_CODE
    args = parse_args(argv)

    settings = build_settings(args.model_id)
    spec = ModelRegistry.get_instance().get_spec(args.model_id)
    creator = ChronosForecasterCreator()

    start = time.perf_counter()
    forecaster = creator.create_forecaster(spec, settings)
    load_seconds = round(time.perf_counter() - start, DECIMALS)
    rss_after_load = current_rss_mb()

    typical = measure_case(
        forecaster,
        spec,
        TYPICAL_CONTEXT_POINTS,
        TYPICAL_PREDICTION_LENGTH,
        args.repetitions,
    )
    maximum = measure_case(
        forecaster,
        spec,
        MAXIMUM_CONTEXT_POINTS,
        MAXIMUM_PREDICTION_LENGTH,
        args.repetitions,
    )
    peak = peak_rss_mb()
    passed = peak <= args.max_rss_mb

    report: dict[str, object] = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": spec.name,
        "python": platform.python_version(),
        "torch": torch.__version__,
        "machine": platform.machine(),
        "cpu_model": cpu_model(),
        "cpu_count": os.cpu_count(),
        "load_seconds": load_seconds,
        "rss_after_load_mb": rss_after_load,
        "peak_rss_mb": peak,
        "limit_mb": args.max_rss_mb,
        "typical": typical,
        "maximum": maximum,
        "passed": passed,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
