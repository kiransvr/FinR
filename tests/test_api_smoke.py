from fastapi.testclient import TestClient
import time

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


def test_logout_revokes_current_token() -> None:
    token = _login("admin", "changeme")
    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout.status_code == 200

    after = client.get(
        "/api/v1/scored-accounts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert after.status_code == 401


def test_admin_can_revoke_other_token() -> None:
    admin_token = _login("admin", "changeme")
    officer_token = _login("field_officer", "officer123")

    revoke = client.post(
        "/api/v1/auth/revoke",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"token": officer_token},
    )
    assert revoke.status_code == 200

    after = client.get(
        "/api/v1/scored-accounts",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert after.status_code == 401


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


def test_metrics_endpoint_exposes_prometheus_text() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.text
    assert "loan_default_api_requests_total" in body
    assert "loan_default_api_errors_total" in body
    assert "loan_default_api_requests_by_route_total" in body


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


def test_async_pipeline_job_submission_and_status() -> None:
    admin_token = _login("admin", "changeme")
    submit = client.post(
        "/api/v1/jobs/pipeline/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert submit.status_code == 202
    payload = submit.json()
    assert payload["job_type"] == "pipeline_run"
    job_id = payload["job_id"]

    status_payload = {}
    for _ in range(20):
        status = client.get(
            f"/api/v1/jobs/{job_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status.status_code == 200
        status_payload = status.json()
        if status_payload["status"] in {"succeeded", "dead_letter"}:
            break
        time.sleep(0.05)

    assert status_payload["status"] in {"queued", "running", "succeeded", "dead_letter"}


def test_async_refresh_job_submission_and_status() -> None:
    admin_token = _login("admin", "changeme")
    submit = client.post(
        "/api/v1/jobs/feedback/refresh-plan",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert submit.status_code == 202
    payload = submit.json()
    assert payload["job_type"] == "refresh_plan"
    job_id = payload["job_id"]

    status = client.get(
        f"/api/v1/jobs/{job_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["status"] in {"queued", "running", "succeeded", "dead_letter"}


def test_requeue_endpoint_returns_not_found_for_unknown_job() -> None:
    admin_token = _login("admin", "changeme")
    response = client.post(
        "/api/v1/jobs/does-not-exist/requeue",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404


def test_cancel_endpoint_can_cancel_queued_job() -> None:
    admin_token = _login("admin", "changeme")
    submit = client.post(
        "/api/v1/jobs/pipeline/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert submit.status_code == 202
    job_id = submit.json()["job_id"]

    canceled = client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert canceled.status_code in {200, 400}
    if canceled.status_code == 200:
        assert canceled.json()["status"] == "canceled"


def test_cancel_endpoint_rejects_non_queued_job_state() -> None:
    admin_token = _login("admin", "changeme")
    submit = client.post(
        "/api/v1/jobs/feedback/refresh-plan",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert submit.status_code == 202
    job_id = submit.json()["job_id"]

    first_cancel = client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    if first_cancel.status_code == 400:
        return

    assert first_cancel.status_code == 200
    assert first_cancel.json()["status"] == "canceled"

    second_cancel = client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second_cancel.status_code == 400


def test_cleanup_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.post(
        "/api/v1/jobs/cleanup?older_than_seconds=0",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_cleanup_endpoint_returns_deleted_count() -> None:
    admin_token = _login("admin", "changeme")

    submit = client.post(
        "/api/v1/jobs/pipeline/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert submit.status_code == 202
    job_id = submit.json()["job_id"]

    cancel = client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cancel.status_code in {200, 400}

    cleanup = client.post(
        "/api/v1/jobs/cleanup?older_than_seconds=0",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cleanup.status_code == 200
    payload = cleanup.json()
    assert payload["status"] == "success"
    assert isinstance(payload["deleted_count"], int)


def test_recover_stale_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.post(
        "/api/v1/jobs/recover-stale?stale_after_seconds=1",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_recover_stale_endpoint_returns_recovered_count() -> None:
    admin_token = _login("admin", "changeme")
    response = client.post(
        "/api/v1/jobs/recover-stale?stale_after_seconds=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["deleted_count"], int)


def test_list_jobs_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs?limit=10",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_list_jobs_endpoint_returns_records() -> None:
    admin_token = _login("admin", "changeme")
    submit = client.post(
        "/api/v1/jobs/pipeline/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert submit.status_code == 202

    response = client.get(
        "/api/v1/jobs?status=queued&limit=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["total"], int)
    assert isinstance(payload["records"], list)
