from http import HTTPStatus

from fastapi.testclient import TestClient

from caudal_ia.main import app
from caudal_ia.readiness import DEFAULT_MODEL_NAME, ModelReadiness


def test_models_route_lists_catalog_and_loaded_state(client: TestClient) -> None:
    previous_readiness = app.state.readiness
    readiness = ModelReadiness(DEFAULT_MODEL_NAME)
    app.state.readiness = readiness

    try:
        response = client.get("/v1/models")

        assert response.status_code == HTTPStatus.OK
        payload = response.json()
        assert [model["name"] for model in payload["models"]] == [
            "autogluon/chronos-2-small",
            "amazon/chronos-bolt-small",
        ]
        assert payload["active"] == DEFAULT_MODEL_NAME
        assert [model["loaded"] for model in payload["models"]] == [False, False]

        readiness.mark_loaded()
        loaded_response = client.get("/v1/models")

        assert loaded_response.status_code == HTTPStatus.OK
        assert [model["loaded"] for model in loaded_response.json()["models"]] == [
            True,
            False,
        ]
    finally:
        app.state.readiness = previous_readiness
