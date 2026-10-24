import pytest

from caudal_ia.model_catalog import (
    CHRONOS_QUANTILE_LEVELS,
    MAX_PREDICTION_LENGTH,
    ModelSpec,
)
from caudal_ia.model_registry import (
    DuplicateModelError,
    ModelRegistry,
    UnknownModelError,
)

TEST_MODEL_PARAMETERS_MILLIONS = 1
TEST_MODEL_NAME = "test/model"


@pytest.fixture(autouse=True)
def reset_model_registry(fresh_model_registry: None) -> None:
    del fresh_model_registry


def test_get_instance_returns_the_same_object() -> None:
    assert ModelRegistry.get_instance() is ModelRegistry.get_instance()


def test_list_specs_returns_default_models_in_registration_order() -> None:
    specs = ModelRegistry.get_instance().list_specs()

    assert [spec.name for spec in specs] == [
        "autogluon/chronos-2-small",
        "amazon/chronos-bolt-small",
        "amazon/chronos-bolt-tiny",
    ]


def test_get_spec_returns_registered_spec() -> None:
    registry = ModelRegistry.get_instance()
    spec = registry.list_specs()[0]

    assert registry.get_spec(spec.name) is spec


def test_get_spec_raises_for_unknown_name() -> None:
    with pytest.raises(UnknownModelError):
        ModelRegistry.get_instance().get_spec(TEST_MODEL_NAME)


def test_register_rejects_duplicate_name() -> None:
    registry = ModelRegistry.get_instance()
    spec = registry.list_specs()[0]

    with pytest.raises(DuplicateModelError):
        registry.register(spec)


def test_register_adds_new_model() -> None:
    registry = ModelRegistry.get_instance()
    spec = ModelSpec(
        name=TEST_MODEL_NAME,
        version="1.0",
        parameters_millions=TEST_MODEL_PARAMETERS_MILLIONS,
        quantile_levels=CHRONOS_QUANTILE_LEVELS,
        max_prediction_length=MAX_PREDICTION_LENGTH,
    )

    registry.register(spec)

    assert registry.get_spec(TEST_MODEL_NAME) is spec
    assert registry.list_specs()[-1] is spec
