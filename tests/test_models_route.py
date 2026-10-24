from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from caudal_ia.config import DEFAULT_CHRONOS_MODEL_ID, get_settings
from caudal_ia.main import app
from caudal_ia.readiness import ModelReadiness


def test_models_route_lists_catalog_and_loaded_state(client: TestClient) -> None:
    previous_readiness = app.state.readiness
    readiness = ModelReadiness(DEFAULT_CHRONOS_MODEL_ID)
    app.state.readiness = readiness

    try:
        response = client.get("/v1/models")

        assert response.status_code == HTTPStatus.OK
        payload = response.json()
        assert [model["name"] for model in payload["models"]] == [
            "autogluon/chronos-2-small",
            "amazon/chronos-bolt-small",
            "amazon/chronos-bolt-tiny",
        ]
        assert payload["active"] == DEFAULT_CHRONOS_MODEL_ID
        assert [model["loaded"] for model in payload["models"]] == [False, False, False]

        readiness.mark_loaded()
        loaded_response = client.get("/v1/models")

        assert loaded_response.status_code == HTTPStatus.OK
        assert [model["loaded"] for model in loaded_response.json()["models"]] == [
            True,
            False,
            False,
        ]
    finally:
        app.state.readiness = previous_readiness


def test_models_route_uses_configured_active_model(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_readiness = app.state.readiness

    try:
        monkeypatch.setenv("CHRONOS_MODEL_ID", "amazon/chronos-bolt-small")
        get_settings.cache_clear()
        readiness = ModelReadiness("amazon/chronos-bolt-small")
        readiness.mark_loaded()
        app.state.readiness = readiness

        response = client.get("/v1/models")

        assert response.status_code == HTTPStatus.OK
        payload = response.json()
        assert payload["active"] == "amazon/chronos-bolt-small"
        assert [model["loaded"] for model in payload["models"]] == [False, True, False]
    finally:
        app.state.readiness = previous_readiness
        monkeypatch.undo()
        get_settings.cache_clear()
