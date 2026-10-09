import pytest
from pydantic import ValidationError

from caudal_ia.config import DEFAULT_CHRONOS_MODEL_ID, Settings, get_settings
from caudal_ia.model_registry import UnknownModelError, resolve_active_model


def test_default_active_model_is_chronos_two_small(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        with monkeypatch.context() as environment:
            environment.delenv("CHRONOS_MODEL_ID", raising=False)
            environment.delenv("CHRONOS_DEVICE", raising=False)
            get_settings.cache_clear()

            assert resolve_active_model(get_settings()).name == DEFAULT_CHRONOS_MODEL_ID
    finally:
        get_settings.cache_clear()


def test_environment_selects_chronos_bolt_small(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        with monkeypatch.context() as environment:
            environment.setenv("CHRONOS_MODEL_ID", "amazon/chronos-bolt-small")
            get_settings.cache_clear()

            assert (
                resolve_active_model(get_settings()).name == "amazon/chronos-bolt-small"
            )
    finally:
        get_settings.cache_clear()


def test_unregistered_model_raises_unknown_model_error() -> None:
    settings = Settings(chronos_model_id="unregistered-model")

    with pytest.raises(UnknownModelError):
        resolve_active_model(settings)


def test_non_cpu_device_fails_settings_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        with monkeypatch.context() as environment:
            environment.setenv("CHRONOS_DEVICE", "cuda")

            with pytest.raises(ValidationError):
                Settings()
    finally:
        get_settings.cache_clear()
