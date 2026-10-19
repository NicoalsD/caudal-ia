from collections.abc import Iterator

import pytest

from caudal_ia.config import get_settings
from caudal_ia.model_loading import load_active_model, start_model_loading
from caudal_ia.model_registry import (
    ModelNotLoadedError,
    ModelRegistry,
    resolve_active_model,
)
from caudal_ia.readiness import ModelReadiness
from tests.fakes import FailingForecasterCreator, FakeForecasterCreator

LOAD_TIMEOUT_SECONDS = 5.0


@pytest.fixture(autouse=True)
def reset_model_registry() -> Iterator[None]:
    ModelRegistry.reset_instance()
    yield
    ModelRegistry.reset_instance()


def test_registry_loads_each_model_only_once() -> None:
    registry = ModelRegistry.get_instance()
    spec = resolve_active_model(get_settings())
    creator = FakeForecasterCreator()

    first = registry.load(spec, creator, get_settings())
    second = registry.load(spec, creator, get_settings())

    assert first is second
    assert registry.get_forecaster(spec.name) is first


def test_registry_reports_models_that_are_not_loaded() -> None:
    with pytest.raises(ModelNotLoadedError):
        ModelRegistry.get_instance().get_forecaster("autogluon/chronos-2-small")


def test_background_loading_marks_the_model_ready() -> None:
    spec = resolve_active_model(get_settings())
    readiness = ModelReadiness(spec.name)

    start_model_loading(spec, FakeForecasterCreator(), get_settings(), readiness)

    assert readiness.wait(LOAD_TIMEOUT_SECONDS) is True
    assert ModelRegistry.get_instance().get_forecaster(spec.name).name == spec.name


def test_failed_loading_keeps_the_model_not_ready() -> None:
    spec = resolve_active_model(get_settings())
    readiness = ModelReadiness(spec.name)

    load_active_model(spec, FailingForecasterCreator(), get_settings(), readiness)

    assert readiness.wait(LOAD_TIMEOUT_SECONDS) is False
    with pytest.raises(ModelNotLoadedError):
        ModelRegistry.get_instance().get_forecaster(spec.name)
