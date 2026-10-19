from http import HTTPStatus

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from caudal_ia.config import Settings, get_settings


def test_docs_are_available_by_default(client: TestClient) -> None:
    response = client.get("/docs")

    assert response.status_code == HTTPStatus.OK


def test_openapi_document_has_application_title(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["info"]["title"] == "caudal-ia"


def test_settings_disable_api_docs_from_environment(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_DOCS_ENABLED", "false")
    get_settings.cache_clear()

    try:
        assert Settings().api_docs_enabled is False
    finally:
        get_settings.cache_clear()
