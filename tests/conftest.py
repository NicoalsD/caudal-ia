import os
from collections.abc import Generator

TEST_SERVICE_TOKEN = "test-service-token-with-at-least-32-bytes"
os.environ.setdefault("IA_SERVICE_TOKEN", TEST_SERVICE_TOKEN)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from caudal_ia.config import get_settings  # noqa: E402
from caudal_ia.main import app  # noqa: E402
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
