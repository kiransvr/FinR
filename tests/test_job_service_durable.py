from __future__ import annotations

import time
from pathlib import Path

from src.application.job_service import JobService


def test_job_state_persists_in_sqlite_queue(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"

    service = JobService(db_path=db_path, poll_interval_seconds=0.01)
    service.register_handler("unit_job", lambda payload: {"echo": payload.get("value", "")})
    service.start_worker()

    submitted = service.submit("unit_job", payload={"value": "ok"})

    final_status = "queued"
    for _ in range(100):
        current = service.get(submitted.job_id)
        assert current is not None
        final_status = current.status
        if final_status in {"succeeded", "dead_letter"}:
            break
        time.sleep(0.01)

    assert final_status == "succeeded"

    reloaded = JobService(db_path=db_path, poll_interval_seconds=0.01)
    loaded = reloaded.get(submitted.job_id)
    assert loaded is not None
    assert loaded.status == "succeeded"
    assert loaded.result == {"echo": "ok"}


def test_job_retries_then_moves_to_dead_letter(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"

    service = JobService(
        db_path=db_path,
        poll_interval_seconds=0.01,
        max_attempts=2,
        retry_backoff_seconds=0.01,
    )

    def _always_fail(_: dict) -> dict:
        raise RuntimeError("boom")

    service.register_handler("failing_job", _always_fail)
    service.start_worker()

    submitted = service.submit("failing_job", payload={})

    final = None
    for _ in range(300):
        current = service.get(submitted.job_id)
        assert current is not None
        if current.status == "dead_letter":
            final = current
            break
        time.sleep(0.01)

    assert final is not None
    assert final.status == "dead_letter"
    assert final.attempts == 2
    assert final.max_attempts == 2
    assert "boom" in (final.error or "")


def test_job_timeout_moves_to_dead_letter_when_single_attempt(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"

    service = JobService(
        db_path=db_path,
        poll_interval_seconds=0.01,
        max_attempts=1,
        retry_backoff_seconds=0.01,
        default_timeout_seconds=0.01,
    )

    def _slow(_: dict) -> dict:
        time.sleep(0.1)
        return {"done": True}

    service.register_handler("slow_job", _slow)
    service.start_worker()

    submitted = service.submit("slow_job", payload={})

    final = None
    for _ in range(300):
        current = service.get(submitted.job_id)
        assert current is not None
        if current.status == "dead_letter":
            final = current
            break
        time.sleep(0.01)

    assert final is not None
    assert final.status == "dead_letter"
    assert "timed out" in (final.error or "").lower()


def test_dead_letter_job_can_be_requeued(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"

    service = JobService(
        db_path=db_path,
        poll_interval_seconds=0.01,
        max_attempts=1,
        retry_backoff_seconds=0.01,
    )

    def _always_fail(_: dict) -> dict:
        raise RuntimeError("first pass fails")

    service.register_handler("requeue_job", _always_fail)
    service.start_worker()

    submitted = service.submit("requeue_job", payload={})

    dead = None
    for _ in range(300):
        current = service.get(submitted.job_id)
        assert current is not None
        if current.status == "dead_letter":
            dead = current
            break
        time.sleep(0.01)

    assert dead is not None
    assert dead.attempts == 1

    service.register_handler("requeue_job", lambda _: {"ok": True})
    requeued = service.requeue_dead_letter(submitted.job_id)
    assert requeued is not None
    assert requeued.status == "queued"
    assert requeued.attempts == 0

    succeeded = None
    for _ in range(300):
        current = service.get(submitted.job_id)
        assert current is not None
        if current.status == "succeeded":
            succeeded = current
            break
        time.sleep(0.01)

    assert succeeded is not None
    assert succeeded.result == {"ok": True}


def test_queued_job_can_be_canceled(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"

    service = JobService(
        db_path=db_path,
        poll_interval_seconds=0.01,
        max_attempts=1,
        retry_backoff_seconds=0.01,
    )
    service.register_handler("cancel_me", lambda _: {"ok": True})

    submitted = service.submit("cancel_me", payload={})
    canceled = service.cancel_queued_job(submitted.job_id)

    assert canceled is not None
    assert canceled.status == "canceled"
