import os
from collections.abc import Generator

TEST_SERVICE_TOKEN = "test-service-token-with-at-least-32-bytes"
os.environ.setdefault("IA_SERVICE_TOKEN", TEST_SERVICE_TOKEN)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from caudal_ia.config import get_settings  # noqa: E402
from caudal_ia.main import app  # noqa: E402
from caudal_ia.model_registry import ModelRegistry  # noqa: E402
from caudal_ia.readiness import ModelReadiness  # noqa: E402
from tests.fakes import FakeForecasterCreator  # noqa: E402

# Tests never download Chronos weights: the lifespan loads a deterministic fake.
app.state.forecaster_creator = FakeForecasterCreator()

AUTHORIZATION_HEADERS = {"Authorization": f"Bearer {TEST_SERVICE_TOKEN}"}


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    get_settings.cache_clear()
    try:
        with TestClient(app, headers=AUTHORIZATION_HEADERS) as test_client:
            yield test_client
    finally:
        get_settings.cache_clear()


@pytest.fixture
def fresh_model_registry() -> Generator[None, None, None]:
    """Empty the registry and mark the model as not loaded around a test.

    The readiness is replaced too: otherwise it would still say "loaded" for a
    registry that no longer holds the model, and the next client could send a
    forecast before its lifespan finishes loading again.
    """
    ModelRegistry.reset_instance()
    app.state.readiness = ModelReadiness(app.state.readiness.model_name)
    yield
    ModelRegistry.reset_instance()
    app.state.readiness = ModelReadiness(app.state.readiness.model_name)
