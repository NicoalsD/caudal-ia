from http import HTTPStatus

from fastapi.testclient import TestClient

from caudal_ia.main import app
from caudal_ia.readiness import DEFAULT_MODEL_NAME, ModelReadiness


def test_health_returns_ok_without_authentication(client: TestClient) -> None:
    response = client.get("/v1/health")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


def test_readiness_reflects_model_load_state(client: TestClient) -> None:
    previous_readiness = app.state.readiness
    readiness = ModelReadiness(DEFAULT_MODEL_NAME)
    app.state.readiness = readiness

    try:
        not_ready_response = client.get("/v1/ready")

        assert not_ready_response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert not_ready_response.headers["Retry-After"] == "30"
        assert not_ready_response.json()["error"]["code"] == "MODEL_NOT_READY"

        readiness.mark_loaded()
        ready_response = client.get("/v1/ready")

        assert ready_response.status_code == HTTPStatus.OK
        assert ready_response.json() == {"status": "ready", "model_loaded": True}
    finally:
        app.state.readiness = previous_readiness
