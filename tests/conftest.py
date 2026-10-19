from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from caudal_ia.config import get_settings
from caudal_ia.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    get_settings.cache_clear()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        get_settings.cache_clear()
