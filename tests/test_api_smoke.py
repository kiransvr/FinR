from fastapi.testclient import TestClient

from src.api.main import app
from src.api.observability import REQUEST_ID_HEADER


client = TestClient(app)


def test_health_endpoint_returns_ok_payload() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "model_loaded" in payload
    assert "pipeline_outputs_available" in payload


def test_liveness_and_readiness_endpoints() -> None:
    live_response = client.get("/api/v1/health/live")
    assert live_response.status_code == 200
    assert live_response.json()["status"] == "alive"

    ready_response = client.get("/api/v1/health/ready")
    assert ready_response.status_code == 200
    ready_payload = ready_response.json()
    assert ready_payload["status"] == "ok"


def test_login_returns_bearer_token_for_admin() -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "changeme"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert isinstance(payload["access_token"], str)
    assert payload["access_token"]


def test_protected_endpoint_requires_token() -> None:
    response = client.get("/api/v1/scored-accounts")
    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "HTTP_401"
    assert "message" in payload["error"]


def test_protected_endpoint_allows_authenticated_call() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "changeme"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/scored-accounts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in (200, 404)


def test_request_id_header_is_returned() -> None:
    request_id = "smoke-test-request-id"
    response = client.get("/api/v1/health", headers={REQUEST_ID_HEADER: request_id})
    assert response.status_code == 200
    assert response.headers.get(REQUEST_ID_HEADER) == request_id


def _login(username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_endpoint_blocks_officer_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.post(
        "/api/v1/pipeline/run",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_admin_endpoint_allows_admin_role() -> None:
    admin_token = _login("admin", "changeme")
    response = client.post(
        "/api/v1/feedback/refresh-plan",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code in (200, 404)
