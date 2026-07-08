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
    if response.status_code == 429:
        from src.api.main import _login_rate_limiter

        with _login_rate_limiter._lock:
            _login_rate_limiter._events.clear()
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


def test_job_stats_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/stats",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_stats_endpoint_returns_counts() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["counts"]["total"], int)


def test_job_type_stats_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/stats-by-type",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_type_stats_endpoint_returns_records() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/stats-by-type?limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["records"], list)
    if payload["records"]:
        first = payload["records"][0]
        assert isinstance(first["job_type"], str)
        assert isinstance(first["queued"], int)
        assert isinstance(first["running"], int)
        assert isinstance(first["dead_letter"], int)
        assert isinstance(first["total"], int)


def test_job_worker_status_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/worker-status",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_worker_status_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/worker-status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["worker_alive"], bool)
    assert isinstance(payload["paused"], bool)
    assert isinstance(payload["running"], int)
    assert isinstance(payload["queued"], int)
    assert isinstance(payload["drained"], bool)


def test_job_queue_age_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/queue-age",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_queue_age_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/queue-age?threshold_seconds=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["queued"], int)
    assert payload["oldest_queued_at"] is None or isinstance(payload["oldest_queued_at"], str)
    assert payload["oldest_queued_age_seconds"] is None or isinstance(payload["oldest_queued_age_seconds"], float)
    assert isinstance(payload["threshold_seconds"], float)
    assert isinstance(payload["breached"], bool)


def test_job_queued_oldest_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/queued-oldest?limit=5",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_queued_oldest_endpoint_returns_records() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/queued-oldest?limit=5",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["total"], int)
    assert isinstance(payload["records"], list)


def test_job_dead_letter_rate_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/dead-letter-rate",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_dead_letter_rate_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/dead-letter-rate?window_seconds=60&threshold_per_minute=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["window_seconds"], float)
    assert isinstance(payload["threshold_per_minute"], float)
    assert isinstance(payload["recent_dead_letter"], int)
    assert isinstance(payload["total_dead_letter"], int)
    assert isinstance(payload["rate_per_minute"], float)
    assert isinstance(payload["breached"], bool)


def test_job_dead_letter_top_types_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/dead-letter-top-types",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_dead_letter_top_types_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/dead-letter-top-types?limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["records"], list)
    if payload["records"]:
        first = payload["records"][0]
        assert isinstance(first["job_type"], str)
        assert isinstance(first["dead_letter"], int)


def test_job_dead_letter_errors_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/dead-letter-errors",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_dead_letter_errors_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/dead-letter-errors?limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["records"], list)
    if payload["records"]:
        first = payload["records"][0]
        assert isinstance(first["error_message"], str)
        assert isinstance(first["dead_letter"], int)


def test_job_dead_letter_recent_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/dead-letter-recent",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_dead_letter_recent_endpoint_returns_records() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/dead-letter-recent?limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["total"], int)
    assert isinstance(payload["records"], list)
    if payload["records"]:
        first = payload["records"][0]
        assert first["status"] == "dead_letter"


def test_job_dead_letter_trend_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/dead-letter-trend",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_dead_letter_trend_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/dead-letter-trend?window_seconds=60",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["window_seconds"], float)
    assert isinstance(payload["recent_count"], int)
    assert isinstance(payload["previous_count"], int)
    assert isinstance(payload["delta"], int)
    assert payload["direction"] in {"up", "down", "flat"}


def test_job_alerts_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_signals_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/signals",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_signals_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/signals",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["severity"] in {"ok", "warning", "critical"}
    assert isinstance(payload["breached"], bool)
    assert isinstance(payload["signals"], list)
    names = {item["name"] for item in payload["signals"]}
    assert {"worker", "queue_age", "dead_letter_rate"}.issubset(names)
    for signal in payload["signals"]:
        assert signal["status"] in {"ok", "warning", "critical"}
        assert isinstance(signal["breached"], bool)
        assert isinstance(signal["details"], dict)


def test_job_alerts_failing_signals_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/failing-signals",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_failing_signals_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/failing-signals",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["severity"] in {"ok", "warning", "critical"}
    assert isinstance(payload["breached"], bool)
    assert isinstance(payload["total_signals"], int)
    assert isinstance(payload["failing_count"], int)
    assert isinstance(payload["signals"], list)
    assert payload["failing_count"] == len(payload["signals"])
    for signal in payload["signals"]:
        assert signal["status"] in {"ok", "warning", "critical"}
        assert isinstance(signal["breached"], bool)
        assert isinstance(signal["details"], dict)
        assert isinstance(signal["recommendation"], str)


def test_job_alerts_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["severity"] in {"ok", "warning", "critical"}
    assert isinstance(payload["breached"], bool)
    assert isinstance(payload["worker_alive"], bool)
    assert isinstance(payload["paused"], bool)
    assert isinstance(payload["queued"], int)
    assert isinstance(payload["running"], int)
    assert isinstance(payload["queue_age_breached"], bool)
    assert isinstance(payload["dead_letter_rate_breached"], bool)
    assert payload["oldest_queued_age_seconds"] is None or isinstance(payload["oldest_queued_age_seconds"], float)
    assert isinstance(payload["dead_letter_rate_per_minute"], float)


def test_job_alerts_recommendations_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/recommendations",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_recommendations_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/recommendations",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["severity"] in {"ok", "warning", "critical"}
    assert isinstance(payload["recommendations"], list)
    assert len(payload["recommendations"]) >= 1
    assert all(isinstance(item, str) for item in payload["recommendations"])


def test_job_alerts_remediation_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/remediation",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_remediation_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/remediation",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["severity"] in {"ok", "warning", "critical"}
    assert isinstance(payload["breached"], bool)
    assert isinstance(payload["failing_count"], int)
    assert isinstance(payload["actions"], list)
    assert isinstance(payload["summary"], str)
    for action in payload["actions"]:
        assert isinstance(action["signal"], str)
        assert action["status"] in {"ok", "warning", "critical"}
        assert isinstance(action["priority"], int)
        assert isinstance(action["action"], str)
        assert isinstance(action["endpoint_hint"], str)


def test_job_alerts_remediation_endpoint_prioritizes_worker_action() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/remediation",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    if payload["actions"]:
        first = payload["actions"][0]
        assert first["priority"] <= payload["actions"][-1]["priority"]


def test_job_alerts_health_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/health",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_health_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/health",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["severity"] in {"ok", "warning", "critical"}
    assert isinstance(payload["healthy"], bool)
    assert isinstance(payload["fail_on_warning"], bool)


def test_job_alerts_health_endpoint_honors_fail_on_warning_flag() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 1,
        "oldest_queued_at": "2000-01-01T00:00:00Z",
        "oldest_queued_age_seconds": 999999.0,
        "threshold_seconds": float(threshold_seconds),
        "breached": True,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        relaxed = client.get(
            "/api/v1/jobs/alerts/health?fail_on_warning=false",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        strict = client.get(
            "/api/v1/jobs/alerts/health?fail_on_warning=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert relaxed.status_code == 200
        assert strict.status_code == 200
        assert relaxed.json()["severity"] == "warning"
        assert strict.json()["severity"] == "warning"
        assert relaxed.json()["healthy"] is True
        assert strict.json()["healthy"] is False
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_gate_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["severity"] in {"ok", "warning", "critical"}
    assert isinstance(payload["breached"], bool)
    assert isinstance(payload["fail_on_warning"], bool)
    assert isinstance(payload["pass_gate"], bool)
    assert isinstance(payload["failing_count"], int)
    assert isinstance(payload["reasons"], list)
    assert all(isinstance(reason, str) for reason in payload["reasons"])


def test_job_alerts_gate_endpoint_honors_fail_on_warning_flag() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 1,
        "oldest_queued_at": "2000-01-01T00:00:00Z",
        "oldest_queued_age_seconds": 999999.0,
        "threshold_seconds": float(threshold_seconds),
        "breached": True,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        relaxed = client.get(
            "/api/v1/jobs/alerts/gate?fail_on_warning=false",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        strict = client.get(
            "/api/v1/jobs/alerts/gate?fail_on_warning=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert relaxed.status_code == 200
        assert strict.status_code == 200
        assert relaxed.json()["severity"] == "warning"
        assert strict.json()["severity"] == "warning"
        assert relaxed.json()["pass_gate"] is True
        assert strict.json()["pass_gate"] is False
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_gate_check_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/check",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_check_endpoint_returns_200_or_503_with_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/check",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code in {200, 503}
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["severity"] in {"ok", "warning", "critical"}
    assert isinstance(payload["breached"], bool)
    assert isinstance(payload["fail_on_warning"], bool)
    assert isinstance(payload["pass_gate"], bool)
    assert isinstance(payload["failing_count"], int)
    assert isinstance(payload["reasons"], list)
    assert all(isinstance(reason, str) for reason in payload["reasons"])


def test_job_alerts_gate_check_endpoint_honors_fail_on_warning_http_status() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 1,
        "oldest_queued_at": "2000-01-01T00:00:00Z",
        "oldest_queued_age_seconds": 999999.0,
        "threshold_seconds": float(threshold_seconds),
        "breached": True,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        relaxed = client.get(
            "/api/v1/jobs/alerts/gate/check?fail_on_warning=false",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        strict = client.get(
            "/api/v1/jobs/alerts/gate/check?fail_on_warning=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert relaxed.status_code == 200
        assert strict.status_code == 503
        assert relaxed.json()["pass_gate"] is True
        assert strict.json()["pass_gate"] is False
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_gate_matrix_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/matrix",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_matrix_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/matrix",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["severity"] in {"ok", "warning", "critical"}
    assert isinstance(payload["breached"], bool)
    assert isinstance(payload["relaxed"], dict)
    assert isinstance(payload["strict"], dict)

    relaxed = payload["relaxed"]
    strict = payload["strict"]
    assert relaxed["fail_on_warning"] is False
    assert strict["fail_on_warning"] is True
    assert isinstance(relaxed["pass_gate"], bool)
    assert isinstance(strict["pass_gate"], bool)
    assert isinstance(relaxed["failing_count"], int)
    assert isinstance(strict["failing_count"], int)
    assert isinstance(relaxed["reasons"], list)
    assert isinstance(strict["reasons"], list)
    assert all(isinstance(reason, str) for reason in relaxed["reasons"])
    assert all(isinstance(reason, str) for reason in strict["reasons"])
    assert relaxed["recommended_status_code"] in {200, 503}
    assert strict["recommended_status_code"] in {200, 503}


def test_job_alerts_gate_matrix_endpoint_honors_warning_mode_split() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 1,
        "oldest_queued_at": "2000-01-01T00:00:00Z",
        "oldest_queued_age_seconds": 999999.0,
        "threshold_seconds": float(threshold_seconds),
        "breached": True,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        response = client.get(
            "/api/v1/jobs/alerts/gate/matrix",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["severity"] == "warning"
        assert payload["relaxed"]["pass_gate"] is True
        assert payload["strict"]["pass_gate"] is False
        assert payload["relaxed"]["recommended_status_code"] == 200
        assert payload["strict"]["recommended_status_code"] == 503
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_gate_advice_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/advice",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_advice_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/advice",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["severity"] in {"ok", "warning", "critical"}
    assert isinstance(payload["breached"], bool)
    assert isinstance(payload["strict_pass"], bool)
    assert isinstance(payload["relaxed_pass"], bool)
    assert payload["recommended_mode"] in {"strict", "relaxed", "block"}
    assert isinstance(payload["deployment_allowed"], bool)
    assert payload["recommended_status_code"] in {200, 503}
    assert isinstance(payload["reasons"], list)
    assert all(isinstance(reason, str) for reason in payload["reasons"])


def test_job_alerts_gate_advice_endpoint_recommends_relaxed_for_warning() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 1,
        "oldest_queued_at": "2000-01-01T00:00:00Z",
        "oldest_queued_age_seconds": 999999.0,
        "threshold_seconds": float(threshold_seconds),
        "breached": True,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        response = client.get(
            "/api/v1/jobs/alerts/gate/advice",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["severity"] == "warning"
        assert payload["relaxed_pass"] is True
        assert payload["strict_pass"] is False
        assert payload["recommended_mode"] == "relaxed"
        assert payload["deployment_allowed"] is True
        assert payload["recommended_status_code"] == 200
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_gate_advice_check_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/advice/check",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_advice_check_endpoint_returns_200_or_503_with_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/advice/check",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code in {200, 503}
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["severity"] in {"ok", "warning", "critical"}
    assert isinstance(payload["strict_pass"], bool)
    assert isinstance(payload["relaxed_pass"], bool)
    assert payload["recommended_mode"] in {"strict", "relaxed", "block"}
    assert isinstance(payload["deployment_allowed"], bool)
    assert payload["recommended_status_code"] in {200, 503}
    assert isinstance(payload["reasons"], list)
    assert all(isinstance(reason, str) for reason in payload["reasons"])


def test_job_alerts_gate_advice_check_endpoint_returns_503_when_blocked() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": False,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 0,
        "oldest_queued_at": None,
        "oldest_queued_age_seconds": None,
        "threshold_seconds": float(threshold_seconds),
        "breached": False,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        response = client.get(
            "/api/v1/jobs/alerts/gate/advice/check",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 503
        payload = response.json()
        assert payload["deployment_allowed"] is False
        assert payload["recommended_mode"] == "block"
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_gate_evaluate_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/evaluate?mode=advice",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_evaluate_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/evaluate?mode=advice",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["severity"] in {"ok", "warning", "critical"}
    assert isinstance(payload["breached"], bool)
    assert payload["mode"] in {"strict", "relaxed", "advice"}
    assert isinstance(payload["pass_gate"], bool)
    assert isinstance(payload["deployment_allowed"], bool)
    assert payload["recommended_status_code"] in {200, 503}
    assert isinstance(payload["reasons"], list)
    assert all(isinstance(reason, str) for reason in payload["reasons"])
    assert payload["recommended_mode"] in {"strict", "relaxed", "block"}


def test_job_alerts_gate_evaluate_endpoint_honors_mode_split() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 1,
        "oldest_queued_at": "2000-01-01T00:00:00Z",
        "oldest_queued_age_seconds": 999999.0,
        "threshold_seconds": float(threshold_seconds),
        "breached": True,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        strict_response = client.get(
            "/api/v1/jobs/alerts/gate/evaluate?mode=strict",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        relaxed_response = client.get(
            "/api/v1/jobs/alerts/gate/evaluate?mode=relaxed",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        advice_response = client.get(
            "/api/v1/jobs/alerts/gate/evaluate?mode=advice",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert strict_response.status_code == 200
        assert relaxed_response.status_code == 200
        assert advice_response.status_code == 200

        strict_payload = strict_response.json()
        relaxed_payload = relaxed_response.json()
        advice_payload = advice_response.json()

        assert strict_payload["pass_gate"] is False
        assert relaxed_payload["pass_gate"] is True
        assert advice_payload["pass_gate"] is True
        assert advice_payload["recommended_mode"] == "relaxed"
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_gate_evaluate_check_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/evaluate/check?mode=advice",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_evaluate_check_endpoint_returns_200_or_503_with_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/evaluate/check?mode=advice",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code in {200, 503}
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["mode"] in {"strict", "relaxed", "advice"}
    assert isinstance(payload["pass_gate"], bool)
    assert isinstance(payload["deployment_allowed"], bool)
    assert payload["recommended_status_code"] in {200, 503}
    assert isinstance(payload["reasons"], list)
    assert all(isinstance(reason, str) for reason in payload["reasons"])


def test_job_alerts_gate_evaluate_check_endpoint_honors_mode_status_codes() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 1,
        "oldest_queued_at": "2000-01-01T00:00:00Z",
        "oldest_queued_age_seconds": 999999.0,
        "threshold_seconds": float(threshold_seconds),
        "breached": True,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        strict_response = client.get(
            "/api/v1/jobs/alerts/gate/evaluate/check?mode=strict",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        relaxed_response = client.get(
            "/api/v1/jobs/alerts/gate/evaluate/check?mode=relaxed",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        advice_response = client.get(
            "/api/v1/jobs/alerts/gate/evaluate/check?mode=advice",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert strict_response.status_code == 503
        assert relaxed_response.status_code == 200
        assert advice_response.status_code == 200

        assert strict_response.json()["mode"] == "strict"
        assert relaxed_response.json()["mode"] == "relaxed"
        assert advice_response.json()["mode"] == "advice"
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_gate_profile_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile?profile=staging",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_profile_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile?profile=staging",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["profile"] in {"prod", "staging", "dev"}
    assert payload["profile_mode"] in {"strict", "advice", "relaxed"}
    assert payload["mode"] in {"strict", "advice", "relaxed"}
    assert isinstance(payload["pass_gate"], bool)
    assert isinstance(payload["deployment_allowed"], bool)
    assert payload["recommended_status_code"] in {200, 503}
    assert isinstance(payload["reasons"], list)


def test_job_alerts_gate_profile_check_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/check?profile=staging",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_profile_check_endpoint_honors_profile_status_codes() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 1,
        "oldest_queued_at": "2000-01-01T00:00:00Z",
        "oldest_queued_age_seconds": 999999.0,
        "threshold_seconds": float(threshold_seconds),
        "breached": True,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        prod_response = client.get(
            "/api/v1/jobs/alerts/gate/profile/check?profile=prod",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        staging_response = client.get(
            "/api/v1/jobs/alerts/gate/profile/check?profile=staging",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        dev_response = client.get(
            "/api/v1/jobs/alerts/gate/profile/check?profile=dev",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert prod_response.status_code == 503
        assert staging_response.status_code == 200
        assert dev_response.status_code == 200

        assert prod_response.json()["profile_mode"] == "strict"
        assert staging_response.json()["profile_mode"] == "advice"
        assert dev_response.json()["profile_mode"] == "relaxed"
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_gate_profile_matrix_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/matrix",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_profile_matrix_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/matrix",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["recommended_profile"] in {"prod", "staging", "dev", "block"}
    assert isinstance(payload["deployment_allowed"], bool)
    assert payload["recommended_status_code"] in {200, 503}
    assert isinstance(payload["profiles"], dict)
    assert {"prod", "staging", "dev"}.issubset(set(payload["profiles"].keys()))


def test_job_alerts_gate_profile_matrix_check_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/matrix/check",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_profile_matrix_check_endpoint_honors_http_status() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 1,
        "oldest_queued_at": "2000-01-01T00:00:00Z",
        "oldest_queued_age_seconds": 999999.0,
        "threshold_seconds": float(threshold_seconds),
        "breached": True,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        warn_response = client.get(
            "/api/v1/jobs/alerts/gate/profile/matrix/check",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert warn_response.status_code == 200
        assert warn_response.json()["recommended_profile"] == "staging"

        job_service.get_worker_status = lambda: {
            "worker_alive": False,
            "paused": False,
            "running": 0,
            "queued": 0,
            "drained": True,
        }
        blocked_response = client.get(
            "/api/v1/jobs/alerts/gate/profile/matrix/check",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert blocked_response.status_code == 503
        assert blocked_response.json()["recommended_profile"] == "block"
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_gate_profile_rollout_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_profile_rollout_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["recommended_profile"] in {"prod", "staging", "dev", "block"}
    assert payload["recommended_action"] in {
        "promote_to_prod",
        "hold_in_staging",
        "continue_in_dev",
        "block_release",
    }
    assert payload["next_profile"] in {"prod", "staging", "dev", None}
    assert isinstance(payload["deployment_allowed"], bool)
    assert payload["recommended_status_code"] in {200, 503}
    assert isinstance(payload["reasons"], list)
    assert isinstance(payload["profiles"], dict)


def test_job_alerts_gate_profile_rollout_check_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout/check",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_profile_rollout_check_endpoint_honors_http_status() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 1,
        "oldest_queued_at": "2000-01-01T00:00:00Z",
        "oldest_queued_age_seconds": 999999.0,
        "threshold_seconds": float(threshold_seconds),
        "breached": True,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        warn_response = client.get(
            "/api/v1/jobs/alerts/gate/profile/rollout/check",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert warn_response.status_code == 200
        assert warn_response.json()["recommended_action"] == "hold_in_staging"

        job_service.get_worker_status = lambda: {
            "worker_alive": False,
            "paused": False,
            "running": 0,
            "queued": 0,
            "drained": True,
        }
        blocked_response = client.get(
            "/api/v1/jobs/alerts/gate/profile/rollout/check",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert blocked_response.status_code == 503
        assert blocked_response.json()["recommended_action"] == "block_release"
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_gate_profile_rollout_plan_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout/plan",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_profile_rollout_plan_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout/plan",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["recommended_profile"] in {"prod", "staging", "dev", "block"}
    assert payload["recommended_action"] in {
        "promote_to_prod",
        "hold_in_staging",
        "continue_in_dev",
        "block_release",
    }
    assert isinstance(payload["promotion_path"], list)
    assert isinstance(payload["blocking_profiles"], list)
    assert isinstance(payload["stages"], list)
    assert len(payload["stages"]) == 3


def test_job_alerts_gate_profile_rollout_plan_check_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout/plan/check",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_profile_rollout_plan_check_endpoint_honors_http_status() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 1,
        "oldest_queued_at": "2000-01-01T00:00:00Z",
        "oldest_queued_age_seconds": 999999.0,
        "threshold_seconds": float(threshold_seconds),
        "breached": True,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        warn_response = client.get(
            "/api/v1/jobs/alerts/gate/profile/rollout/plan/check",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert warn_response.status_code == 200
        assert warn_response.json()["recommended_action"] == "hold_in_staging"

        job_service.get_worker_status = lambda: {
            "worker_alive": False,
            "paused": False,
            "running": 0,
            "queued": 0,
            "drained": True,
        }
        blocked_response = client.get(
            "/api/v1/jobs/alerts/gate/profile/rollout/plan/check",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert blocked_response.status_code == 503
        assert blocked_response.json()["recommended_action"] == "block_release"
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_gate_profile_rollout_summary_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout/summary",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_profile_rollout_summary_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout/summary",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["recommended_profile"] in {"prod", "staging", "dev", "block"}
    assert payload["recommended_action"] in {
        "promote_to_prod",
        "hold_in_staging",
        "continue_in_dev",
        "block_release",
    }
    assert payload["release_readiness"] in {
        "ready_for_prod",
        "ready_for_staging",
        "dev_only",
        "blocked",
    }
    assert payload["highest_eligible_profile"] in {"prod", "staging", "dev", None}
    assert isinstance(payload["eligible_stages"], int)
    assert isinstance(payload["blocked_stages"], int)
    assert isinstance(payload["total_stages"], int)
    assert isinstance(payload["blocking_profiles"], list)
    assert isinstance(payload["reasons"], list)
    assert isinstance(payload["suppression_active"], bool)
    assert payload["suppress_warning_until"] is None or isinstance(payload["suppress_warning_until"], str)
    assert payload["suppression_reason"] is None or isinstance(payload["suppression_reason"], str)
    assert isinstance(payload["suppressed"], bool)


def test_job_alerts_gate_profile_rollout_summary_check_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout/summary/check",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_profile_rollout_summary_check_endpoint_honors_http_status() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 1,
        "oldest_queued_at": "2000-01-01T00:00:00Z",
        "oldest_queued_age_seconds": 999999.0,
        "threshold_seconds": float(threshold_seconds),
        "breached": True,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        warn_response = client.get(
            "/api/v1/jobs/alerts/gate/profile/rollout/summary/check?suppress_warning_until=2999-01-01T00:00:00Z&suppression_reason=maintenance-window",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert warn_response.status_code == 200
        assert warn_response.json()["release_readiness"] == "ready_for_staging"
        assert warn_response.json()["suppression_active"] is True
        assert warn_response.json()["suppressed"] is True

        job_service.get_worker_status = lambda: {
            "worker_alive": False,
            "paused": False,
            "running": 0,
            "queued": 0,
            "drained": True,
        }
        blocked_response = client.get(
            "/api/v1/jobs/alerts/gate/profile/rollout/summary/check?suppress_warning_until=2999-01-01T00:00:00Z&suppression_reason=maintenance-window",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert blocked_response.status_code == 503
        assert blocked_response.json()["release_readiness"] == "blocked"
        assert blocked_response.json()["suppression_active"] is True
        assert blocked_response.json()["suppressed"] is False
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_gate_profile_rollout_policy_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout/policy?policy=balanced",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_profile_rollout_policy_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout/policy?policy=balanced",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["policy"] in {"strict-prod", "balanced", "conservative"}
    assert isinstance(payload["queue_age_threshold_seconds"], float)
    assert isinstance(payload["dead_letter_window_seconds"], float)
    assert isinstance(payload["dead_letter_threshold_per_minute"], float)
    assert payload["release_readiness"] in {
        "ready_for_prod",
        "ready_for_staging",
        "dev_only",
        "blocked",
    }
    assert isinstance(payload["deployment_allowed"], bool)


def test_job_alerts_gate_profile_rollout_policy_endpoint_supports_policy_presets() -> None:
    admin_token = _login("admin", "changeme")

    strict_response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout/policy?policy=strict-prod",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    conservative_response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout/policy?policy=conservative",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert strict_response.status_code == 200
    assert conservative_response.status_code == 200

    strict_payload = strict_response.json()
    conservative_payload = conservative_response.json()
    assert strict_payload["policy"] == "strict-prod"
    assert conservative_payload["policy"] == "conservative"
    assert strict_payload["queue_age_threshold_seconds"] == 120.0
    assert conservative_payload["queue_age_threshold_seconds"] == 240.0


def test_job_alerts_gate_profile_rollout_policy_check_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout/policy/check?policy=balanced",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_profile_rollout_policy_check_endpoint_returns_200_or_503_with_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/profile/rollout/policy/check?policy=balanced",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code in {200, 503}
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["policy"] in {"strict-prod", "balanced", "conservative"}
    assert isinstance(payload["deployment_allowed"], bool)
    assert payload["recommended_status_code"] in {200, 503}
    assert payload["release_readiness"] in {
        "ready_for_prod",
        "ready_for_staging",
        "dev_only",
        "blocked",
    }


def test_job_alerts_gate_profile_rollout_policy_check_endpoint_honors_http_status() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_worker_status = job_service.get_worker_status
    original_get_queue_age_status = job_service.get_queue_age_status
    original_get_dead_letter_rate_status = job_service.get_dead_letter_rate_status
    job_service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }
    job_service.get_queue_age_status = lambda threshold_seconds=300.0: {
        "queued": 1,
        "oldest_queued_at": "2000-01-01T00:00:00Z",
        "oldest_queued_age_seconds": 999999.0,
        "threshold_seconds": float(threshold_seconds),
        "breached": True,
    }
    job_service.get_dead_letter_rate_status = lambda window_seconds=3600.0, threshold_per_minute=1.0: {
        "window_seconds": float(window_seconds),
        "threshold_per_minute": float(threshold_per_minute),
        "recent_dead_letter": 0,
        "total_dead_letter": 0,
        "rate_per_minute": 0.0,
        "breached": False,
    }
    try:
        warn_response = client.get(
            "/api/v1/jobs/alerts/gate/profile/rollout/policy/check?policy=balanced",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert warn_response.status_code == 200
        assert warn_response.json()["release_readiness"] == "ready_for_staging"

        job_service.get_worker_status = lambda: {
            "worker_alive": False,
            "paused": False,
            "running": 0,
            "queued": 0,
            "drained": True,
        }
        blocked_response = client.get(
            "/api/v1/jobs/alerts/gate/profile/rollout/policy/check?policy=balanced",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert blocked_response.status_code == 503
        assert blocked_response.json()["release_readiness"] == "blocked"
    finally:
        job_service.get_worker_status = original_get_worker_status
        job_service.get_queue_age_status = original_get_queue_age_status
        job_service.get_dead_letter_rate_status = original_get_dead_letter_rate_status


def test_job_alerts_incidents_annotate_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.post(
        "/api/v1/jobs/alerts/incidents/annotate",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={"summary": "note", "scope": "rollout", "details": {"k": "v"}},
    )
    assert response.status_code == 403


def test_job_alerts_incidents_annotate_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.post(
        "/api/v1/jobs/alerts/incidents/annotate",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"summary": "maintenance note", "scope": "rollout", "details": {"ticket": "OPS-999"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    record = payload["record"]
    assert isinstance(record["annotation_id"], str)
    assert record["scope"] == "rollout"
    assert record["summary"] == "maintenance note"
    assert isinstance(record["details"], dict)
    assert record["created_by"] == "admin"
    assert record["created_by_role"] == "admin"


def test_job_alerts_incidents_list_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/incidents?limit=10",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_incidents_list_endpoint_returns_records_and_supports_scope() -> None:
    admin_token = _login("admin", "changeme")

    create_rollout = client.post(
        "/api/v1/jobs/alerts/incidents/annotate",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"summary": "rollout note", "scope": "rollout", "details": {}},
    )
    create_canary = client.post(
        "/api/v1/jobs/alerts/incidents/annotate",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"summary": "canary note", "scope": "canary", "details": {}},
    )
    assert create_rollout.status_code == 200
    assert create_canary.status_code == 200

    response = client.get(
        "/api/v1/jobs/alerts/incidents?limit=10&scope=rollout",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["total"], int)
    assert isinstance(payload["records"], list)
    assert all(record["scope"] == "rollout" for record in payload["records"])


def test_job_alerts_gate_decisions_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/alerts/gate/decisions?limit=10",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_alerts_gate_decisions_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/alerts/gate/decisions?limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["total"], int)
    assert isinstance(payload["records"], list)
    if payload["records"]:
        first = payload["records"][0]
        assert isinstance(first["decision_id"], str)
        assert isinstance(first["decision_type"], str)
        assert isinstance(first["allowed"], bool)
        assert first["status_code"] in {200, 503}
        assert isinstance(first["payload"], dict)


def test_job_alerts_gate_decisions_endpoint_captures_check_calls() -> None:
    admin_token = _login("admin", "changeme")

    decision_response = client.get(
        "/api/v1/jobs/alerts/gate/check?fail_on_warning=false",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert decision_response.status_code in {200, 503}

    history_response = client.get(
        "/api/v1/jobs/alerts/gate/decisions?limit=50&decision_type=alerts_gate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert history_response.status_code == 200
    payload = history_response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["records"], list)
    assert payload["records"]
    assert all(record["decision_type"] == "alerts_gate" for record in payload["records"])


def test_job_restart_worker_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.post(
        "/api/v1/jobs/restart-worker",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_restart_worker_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.post(
        "/api/v1/jobs/restart-worker",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["restarted"], bool)
    assert isinstance(payload["worker_alive"], bool)
    assert isinstance(payload["paused"], bool)
    assert isinstance(payload["running"], int)
    assert isinstance(payload["queued"], int)
    assert isinstance(payload["drained"], bool)


def test_job_ensure_worker_alive_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.post(
        "/api/v1/jobs/ensure-worker-alive",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_job_ensure_worker_alive_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.post(
        "/api/v1/jobs/ensure-worker-alive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["started"], bool)
    assert isinstance(payload["worker_alive"], bool)
    assert isinstance(payload["paused"], bool)
    assert isinstance(payload["running"], int)
    assert isinstance(payload["queued"], int)
    assert isinstance(payload["drained"], bool)


def test_pipeline_async_submission_is_deduplicated_by_default() -> None:
    admin_token = _login("admin", "changeme")
    first = client.post(
        "/api/v1/jobs/pipeline/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 202

    second = client.post(
        "/api/v1/jobs/pipeline/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]


def test_pipeline_async_force_submission_creates_new_job() -> None:
    admin_token = _login("admin", "changeme")
    first = client.post(
        "/api/v1/jobs/pipeline/run?force=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    second = client.post(
        "/api/v1/jobs/pipeline/run?force=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] != second.json()["job_id"]


def test_pipeline_async_returns_429_when_queue_capacity_exceeded() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_limit = job_service._max_queued_jobs
    try:
        existing_queued = int(job_service.get_job_stats()["counts"]["queued"])
        job_service._max_queued_jobs = existing_queued + 1
        first = client.post(
            "/api/v1/jobs/pipeline/run?force=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert first.status_code == 202

        second = client.post(
            "/api/v1/jobs/pipeline/run?force=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert second.status_code == 429
    finally:
        job_service._max_queued_jobs = original_limit


def test_pause_and_resume_endpoints_require_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")

    pause = client.post(
        "/api/v1/jobs/pause",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert pause.status_code == 403

    resume = client.post(
        "/api/v1/jobs/resume",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert resume.status_code == 403


def test_pause_and_resume_endpoints_toggle_stats_paused_flag() -> None:
    admin_token = _login("admin", "changeme")

    pause = client.post(
        "/api/v1/jobs/pause",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert pause.status_code == 200

    paused_stats = client.get(
        "/api/v1/jobs/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert paused_stats.status_code == 200
    assert paused_stats.json()["paused"] is True

    resume = client.post(
        "/api/v1/jobs/resume",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resume.status_code == 200

    resumed_stats = client.get(
        "/api/v1/jobs/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resumed_stats.status_code == 200
    assert resumed_stats.json()["paused"] is False


def test_resume_with_require_drained_returns_409_when_not_drained() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_drain_status = job_service.get_drain_status
    job_service.pause_processing()
    job_service.get_drain_status = lambda: {"paused": True, "running": 1, "queued": 0, "drained": False}
    try:
        response = client.post(
            "/api/v1/jobs/resume?require_drained=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 409
    finally:
        job_service.get_drain_status = original_get_drain_status
        job_service.resume_processing()


def test_resume_with_require_drained_succeeds_when_drained() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_get_drain_status = job_service.get_drain_status
    job_service.pause_processing()
    job_service.get_drain_status = lambda: {"paused": True, "running": 0, "queued": 0, "drained": True}
    try:
        response = client.post(
            "/api/v1/jobs/resume?require_drained=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
    finally:
        job_service.get_drain_status = original_get_drain_status
        job_service.resume_processing()


def test_resume_safe_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.post(
        "/api/v1/jobs/resume-safe?timeout_seconds=0",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_resume_safe_times_out_without_resuming() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_wait_for_drain = job_service.wait_for_drain
    job_service.pause_processing()
    job_service.wait_for_drain = lambda timeout_seconds=30.0: {
        "paused": True,
        "running": 1,
        "queued": 0,
        "drained": False,
        "timed_out": True,
        "timeout_seconds": float(timeout_seconds),
    }
    try:
        response = client.post(
            "/api/v1/jobs/resume-safe?timeout_seconds=0",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["resumed"] is False
        assert payload["timed_out"] is True
    finally:
        job_service.wait_for_drain = original_wait_for_drain
        job_service.resume_processing()


def test_resume_safe_resumes_when_drain_succeeds() -> None:
    admin_token = _login("admin", "changeme")

    from src.api.main import get_job_service

    job_service = get_job_service()
    original_wait_for_drain = job_service.wait_for_drain
    job_service.pause_processing()
    job_service.wait_for_drain = lambda timeout_seconds=30.0: {
        "paused": True,
        "running": 0,
        "queued": 0,
        "drained": True,
        "timed_out": False,
        "timeout_seconds": float(timeout_seconds),
    }
    try:
        response = client.post(
            "/api/v1/jobs/resume-safe?timeout_seconds=0",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["resumed"] is True
        assert payload["drained"] is True
    finally:
        job_service.wait_for_drain = original_wait_for_drain
        job_service.resume_processing()


def test_async_submit_returns_423_when_processing_paused() -> None:
    admin_token = _login("admin", "changeme")

    pause = client.post(
        "/api/v1/jobs/pause",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert pause.status_code == 200

    try:
        submit = client.post(
            "/api/v1/jobs/pipeline/run",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert submit.status_code == 423
    finally:
        resume = client.post(
            "/api/v1/jobs/resume",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resume.status_code == 200


def test_bulk_cancel_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.post(
        "/api/v1/jobs/cancel-queued",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_bulk_cancel_endpoint_returns_affected_count() -> None:
    admin_token = _login("admin", "changeme")
    first = client.post(
        "/api/v1/jobs/pipeline/run?force=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    second = client.post(
        "/api/v1/jobs/feedback/refresh-plan?force=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code in {202, 429, 423}
    assert second.status_code in {202, 429, 423}

    response = client.post(
        "/api/v1/jobs/cancel-queued",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["affected_count"], int)


def test_bulk_cancel_endpoint_accepts_limit_parameter() -> None:
    admin_token = _login("admin", "changeme")
    response = client.post(
        "/api/v1/jobs/cancel-queued?limit=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["affected_count"], int)


def test_drain_status_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.get(
        "/api/v1/jobs/drain-status",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_drain_status_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.get(
        "/api/v1/jobs/drain-status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["paused"], bool)
    assert isinstance(payload["running"], int)
    assert isinstance(payload["queued"], int)
    assert isinstance(payload["drained"], bool)


def test_drain_wait_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.post(
        "/api/v1/jobs/drain-wait?timeout_seconds=0",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_drain_wait_endpoint_returns_shape() -> None:
    admin_token = _login("admin", "changeme")
    response = client.post(
        "/api/v1/jobs/drain-wait?timeout_seconds=0",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["paused"], bool)
    assert isinstance(payload["running"], int)
    assert isinstance(payload["queued"], int)
    assert isinstance(payload["drained"], bool)
    assert isinstance(payload["timed_out"], bool)
    assert isinstance(payload["timeout_seconds"], float)


def test_bulk_dead_letter_requeue_endpoint_requires_admin_role() -> None:
    officer_token = _login("field_officer", "officer123")
    response = client.post(
        "/api/v1/jobs/requeue-dead-letter",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 403


def test_bulk_dead_letter_requeue_endpoint_returns_affected_count() -> None:
    admin_token = _login("admin", "changeme")
    response = client.post(
        "/api/v1/jobs/requeue-dead-letter?limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["affected_count"], int)


def test_bulk_dead_letter_requeue_endpoint_supports_dry_run() -> None:
    admin_token = _login("admin", "changeme")
    response = client.post(
        "/api/v1/jobs/requeue-dead-letter?dry_run=true&limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert "Dry-run" in payload["message"]
    assert isinstance(payload["affected_count"], int)
