import logging
import math

import pytest

from caudal_ia.config import get_settings
from caudal_ia.forecasting.decorators import CachingForecaster, TimingForecaster
from caudal_ia.model_registry import resolve_active_model
from tests.fakes import DeterministicForecaster, FakeForecasterCreator

LEVELS = (0.1, 0.5, 0.9)
CONTEXT = (2.5, 2.25, 2.125)
SECRET_LOOKING_VALUE = "2.125"
TTL_SECONDS = 10.0
TWO_MODEL_CALLS = 2
THREE_MODEL_CALLS = 3


class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_timing_logs_latency_without_series_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    forecaster = TimingForecaster(DeterministicForecaster())

    with caplog.at_level(logging.INFO):
        forecaster.predict_quantiles(CONTEXT, 1, LEVELS)

    assert "latency_ms=" in caplog.text
    assert "context_points=3" in caplog.text
    assert SECRET_LOOKING_VALUE not in caplog.text


def test_decorators_keep_name_and_version() -> None:
    wrapped = DeterministicForecaster("name", "version")
    forecaster = CachingForecaster(TimingForecaster(wrapped), 1, TTL_SECONDS)

    assert (forecaster.name, forecaster.version) == ("name", "version")


def test_identical_requests_hit_the_cache() -> None:
    wrapped = DeterministicForecaster()
    forecaster = CachingForecaster(wrapped, 4, TTL_SECONDS)

    first = forecaster.predict_quantiles(CONTEXT, 2, LEVELS)
    second = forecaster.predict_quantiles(list(CONTEXT), 2, LEVELS)

    assert first is second
    assert wrapped.calls == 1


def test_any_difference_in_the_request_misses_the_cache() -> None:
    wrapped = DeterministicForecaster()
    forecaster = CachingForecaster(wrapped, 4, TTL_SECONDS)

    forecaster.predict_quantiles(CONTEXT, 2, LEVELS)
    forecaster.predict_quantiles(CONTEXT, 3, LEVELS)
    forecaster.predict_quantiles((*CONTEXT[:-1], math.nan, CONTEXT[-1]), 2, LEVELS)

    assert wrapped.calls == THREE_MODEL_CALLS


def test_entries_expire_after_the_ttl() -> None:
    clock = ManualClock()
    wrapped = DeterministicForecaster()
    forecaster = CachingForecaster(wrapped, 4, TTL_SECONDS, clock=clock)

    forecaster.predict_quantiles(CONTEXT, 1, LEVELS)
    clock.now = TTL_SECONDS
    forecaster.predict_quantiles(CONTEXT, 1, LEVELS)

    assert wrapped.calls == TWO_MODEL_CALLS


def test_least_recently_used_entry_is_evicted() -> None:
    wrapped = DeterministicForecaster()
    forecaster = CachingForecaster(wrapped, 1, TTL_SECONDS)

    forecaster.predict_quantiles(CONTEXT, 1, LEVELS)
    forecaster.predict_quantiles(CONTEXT, 2, LEVELS)
    forecaster.predict_quantiles(CONTEXT, 1, LEVELS)

    assert wrapped.calls == THREE_MODEL_CALLS


def test_creator_applies_cache_only_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = resolve_active_model(get_settings())
    try:
        enabled = FakeForecasterCreator().create(spec, get_settings())
        monkeypatch.setenv("FORECAST_CACHE_SIZE", "0")
        get_settings.cache_clear()
        disabled = FakeForecasterCreator().create(spec, get_settings())
    finally:
        get_settings.cache_clear()

    assert isinstance(enabled, CachingForecaster)
    assert isinstance(disabled, TimingForecaster)
