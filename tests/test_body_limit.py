from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from caudal_ia.config import get_settings

FORECAST_PATH = "/v1/forecasts"
JSON_HEADERS = {"Content-Type": "application/json"}
BODY_LIMIT_BYTES = 2048
CHUNK_BYTES = 1024
OVER_LIMIT_CHUNKS = 4
UNDER_LIMIT_CHUNKS = 1
PAYLOAD_TOO_LARGE_CODE = "PAYLOAD_TOO_LARGE"


def chunked_body(chunks: int) -> Iterator[bytes]:
    """Yield the body in pieces, so httpx sends it without Content-Length."""
    for _ in range(chunks):
        yield b"x" * CHUNK_BYTES


@pytest.fixture
def small_body_limit(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("MAX_BODY_BYTES", str(BODY_LIMIT_BYTES))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_chunked_body_over_limit_returns_payload_too_large(
    client: TestClient, small_body_limit: None
) -> None:
    response = client.post(
        FORECAST_PATH,
        content=chunked_body(OVER_LIMIT_CHUNKS),
        headers=JSON_HEADERS,
    )

    assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert response.json()["error"]["code"] == PAYLOAD_TOO_LARGE_CODE
    assert response.json()["error"]["details"] == {"limit_bytes": BODY_LIMIT_BYTES}


def test_chunked_body_within_limit_is_not_rejected_for_size(
    client: TestClient, small_body_limit: None
) -> None:
    response = client.post(
        FORECAST_PATH,
        content=chunked_body(UNDER_LIMIT_CHUNKS),
        headers=JSON_HEADERS,
    )

    assert response.status_code != HTTPStatus.REQUEST_ENTITY_TOO_LARGE
