from __future__ import annotations

import time
from pathlib import Path
import sqlite3

from src.application.job_service import JobService
from src.application.job_service import QueueCapacityExceededError
from src.application.job_service import ProcessingPausedError


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


def test_cleanup_removes_terminal_jobs(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"

    service = JobService(db_path=db_path, poll_interval_seconds=0.01)
    service.register_handler("cleanup_me", lambda _: {"ok": True})

    submitted = service.submit("cleanup_me", payload={})
    canceled = service.cancel_queued_job(submitted.job_id)
    assert canceled is not None
    assert canceled.status == "canceled"

    deleted = service.cleanup_terminal_jobs(older_than_seconds=0)
    assert deleted >= 1
    assert service.get(submitted.job_id) is None


def test_cleanup_does_not_remove_active_jobs(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"

    service = JobService(db_path=db_path, poll_interval_seconds=0.01)
    service.register_handler("keep_me", lambda _: {"ok": True})

    submitted = service.submit("keep_me", payload={})
    deleted = service.cleanup_terminal_jobs(older_than_seconds=0)

    assert deleted == 0
    assert service.get(submitted.job_id) is not None


def test_recover_stale_running_job_requeues_when_attempts_remain(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, max_attempts=3)
    service.register_handler("stale_job", lambda _: {"ok": True})

    submitted = service.submit("stale_job", payload={})

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE job_queue
            SET status = 'running', attempts = 1, updated_at = '2000-01-01T00:00:00Z'
            WHERE job_id = ?
            """,
            (submitted.job_id,),
        )

    recovered = service.recover_stale_running_jobs(stale_after_seconds=1)
    assert recovered == 1

    state = service.get(submitted.job_id)
    assert state is not None
    assert state.status == "queued"
    assert "Recovered stale running job" in (state.error or "")


def test_recover_stale_running_job_dead_letters_when_attempts_exhausted(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, max_attempts=2)
    service.register_handler("stale_job", lambda _: {"ok": True})

    submitted = service.submit("stale_job", payload={})

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE job_queue
            SET status = 'running', attempts = 2, max_attempts = 2, updated_at = '2000-01-01T00:00:00Z'
            WHERE job_id = ?
            """,
            (submitted.job_id,),
        )

    recovered = service.recover_stale_running_jobs(stale_after_seconds=1)
    assert recovered == 1

    state = service.get(submitted.job_id)
    assert state is not None
    assert state.status == "dead_letter"


def test_list_jobs_filters_by_status(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("list_job", lambda _: {"ok": True})

    first = service.submit("list_job", payload={})
    second = service.submit("list_job", payload={})
    canceled = service.cancel_queued_job(first.job_id)

    assert canceled is not None
    assert canceled.status == "canceled"

    queued_jobs = service.list_jobs(status_filter="queued", limit=20)
    canceled_jobs = service.list_jobs(status_filter="canceled", limit=20)

    assert any(job.job_id == second.job_id for job in queued_jobs)
    assert all(job.status == "queued" for job in queued_jobs)
    assert len(canceled_jobs) == 1
    assert canceled_jobs[0].job_id == first.job_id


def test_list_jobs_respects_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("list_job", lambda _: {"ok": True})

    service.submit("list_job", payload={})
    service.submit("list_job", payload={})
    service.submit("list_job", payload={})

    limited = service.list_jobs(limit=2)
    assert len(limited) == 2


def test_get_job_stats_returns_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("stats_job", lambda _: {"ok": True})

    queued = service.submit("stats_job", payload={})
    canceled = service.submit("stats_job", payload={})
    canceled_state = service.cancel_queued_job(canceled.job_id)

    assert canceled_state is not None
    assert canceled_state.status == "canceled"

    stats = service.get_job_stats()
    counts = stats["counts"]
    assert counts["total"] >= 2
    assert counts["queued"] >= 1
    assert counts["canceled"] >= 1

    oldest = stats["oldest"]
    assert oldest["queued"] is not None


def test_submit_deduplicated_reuses_active_job(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("dedupe_job", lambda _: {"ok": True})

    first, first_created = service.submit_deduplicated("dedupe_job", payload={})
    second, second_created = service.submit_deduplicated("dedupe_job", payload={})

    assert first_created is True
    assert second_created is False
    assert first.job_id == second.job_id


def test_stop_worker_prevents_further_processing(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, poll_interval_seconds=0.01)
    service.register_handler("stop_job", lambda _: {"ok": True})
    service.start_worker()
    service.stop_worker()

    submitted = service.submit("stop_job", payload={})
    time.sleep(0.05)

    state = service.get(submitted.job_id)
    assert state is not None
    assert state.status == "queued"


def test_is_worker_alive_reflects_start_and_stop(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, poll_interval_seconds=0.01)
    service.register_handler("alive_job", lambda _: {"ok": True})

    assert service.is_worker_alive() is False
    service.start_worker()
    assert service.is_worker_alive() is True

    service.stop_worker()
    assert service.is_worker_alive() is False


def test_restart_worker_restores_processing_after_stop(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, poll_interval_seconds=0.01)
    service.register_handler("restart_job", lambda _: {"ok": True})

    service.start_worker()
    service.stop_worker()
    assert service.is_worker_alive() is False

    restarted = service.restart_worker()
    assert restarted is True
    assert service.is_worker_alive() is True

    submitted = service.submit("restart_job", payload={})
    for _ in range(200):
        state = service.get(submitted.job_id)
        assert state is not None
        if state.status == "succeeded":
            break
        time.sleep(0.01)

    state = service.get(submitted.job_id)
    assert state is not None
    assert state.status == "succeeded"


def test_get_worker_status_returns_expected_shape(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("status_job", lambda _: {"ok": True})
    service.pause_processing()

    status = service.get_worker_status()
    assert isinstance(status["worker_alive"], bool)
    assert status["paused"] is True
    assert isinstance(status["running"], int)
    assert isinstance(status["queued"], int)
    assert isinstance(status["drained"], bool)


def test_submit_raises_when_queue_capacity_exceeded(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, max_queued_jobs=1)
    service.register_handler("capacity_job", lambda _: {"ok": True})

    service.submit("capacity_job", payload={})
    try:
        service.submit("capacity_job", payload={})
        assert False, "Expected QueueCapacityExceededError"
    except QueueCapacityExceededError:
        pass


def test_pause_and_resume_processing_controls_worker_execution(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, poll_interval_seconds=0.01)
    def _slow(_: dict) -> dict:
        time.sleep(0.2)
        return {"ok": True}

    service.register_handler("pause_job", _slow)
    service.start_worker()
    submitted = service.submit("pause_job", payload={})
    service.pause_processing()
    time.sleep(0.05)

    paused_state = service.get(submitted.job_id)
    assert paused_state is not None
    assert paused_state.status in {"queued", "running"}

    service.resume_processing()
    succeeded = None
    for _ in range(200):
        current = service.get(submitted.job_id)
        assert current is not None
        if current.status == "succeeded":
            succeeded = current
            break
        time.sleep(0.01)

    assert succeeded is not None


def test_submit_raises_when_processing_paused(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("paused_job", lambda _: {"ok": True})
    service.pause_processing()

    try:
        service.submit("paused_job", payload={})
        assert False, "Expected ProcessingPausedError"
    except ProcessingPausedError:
        pass


def test_cancel_queued_jobs_cancels_all_queued(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("bulk_job", lambda _: {"ok": True})

    first = service.submit("bulk_job", payload={})
    second = service.submit("bulk_job", payload={})

    affected = service.cancel_queued_jobs()
    assert affected >= 2

    first_state = service.get(first.job_id)
    second_state = service.get(second.job_id)
    assert first_state is not None and first_state.status == "canceled"
    assert second_state is not None and second_state.status == "canceled"


def test_cancel_queued_jobs_filters_by_job_type(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("bulk_a", lambda _: {"ok": True})
    service.register_handler("bulk_b", lambda _: {"ok": True})

    a = service.submit("bulk_a", payload={})
    b = service.submit("bulk_b", payload={})

    affected = service.cancel_queued_jobs(job_type="bulk_a")
    assert affected == 1

    a_state = service.get(a.job_id)
    b_state = service.get(b.job_id)
    assert a_state is not None and a_state.status == "canceled"
    assert b_state is not None and b_state.status == "queued"


def test_cancel_queued_jobs_honors_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("bulk_limited", lambda _: {"ok": True})

    first = service.submit("bulk_limited", payload={})
    second = service.submit("bulk_limited", payload={})

    affected = service.cancel_queued_jobs(limit=1)
    assert affected == 1

    first_state = service.get(first.job_id)
    second_state = service.get(second.job_id)
    assert first_state is not None
    assert second_state is not None
    statuses = {first_state.status, second_state.status}
    assert statuses == {"canceled", "queued"}


def test_get_drain_status_reflects_pause_and_running_state(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, poll_interval_seconds=0.01)

    def _slow(_: dict) -> dict:
        time.sleep(0.2)
        return {"ok": True}

    service.register_handler("drain_job", _slow)
    service.start_worker()
    service.submit("drain_job", payload={})

    time.sleep(0.02)
    service.pause_processing()
    status = service.get_drain_status()
    assert status["paused"] is True
    assert isinstance(status["running"], int)
    assert isinstance(status["queued"], int)
    assert isinstance(status["drained"], bool)


def test_wait_for_drain_returns_drained_when_paused_and_no_running_jobs(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("drain_wait_job", lambda _: {"ok": True})
    service.pause_processing()

    status = service.wait_for_drain(timeout_seconds=0.1)
    assert status["paused"] is True
    assert status["drained"] is True
    assert status["timed_out"] is False


def test_wait_for_drain_times_out_when_not_drained(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("drain_wait_job", lambda _: {"ok": True})

    status = service.wait_for_drain(timeout_seconds=0.05, poll_interval_seconds=0.01)
    assert status["drained"] is False
    assert status["timed_out"] is True


def test_get_job_type_stats_returns_aggregated_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("type_a", lambda _: {"ok": True})
    service.register_handler("type_b", lambda _: {"ok": True})

    a = service.submit("type_a", payload={})
    b = service.submit("type_b", payload={})
    canceled = service.cancel_queued_job(b.job_id)

    assert canceled is not None
    assert canceled.status == "canceled"

    stats = service.get_job_type_stats(limit=10)
    assert len(stats) >= 2
    by_type = {str(row["job_type"]): row for row in stats}

    assert "type_a" in by_type
    assert int(by_type["type_a"]["total"]) >= 1
    assert int(by_type["type_a"]["queued"]) >= 1

    assert "type_b" in by_type
    assert int(by_type["type_b"]["total"]) >= 1
    assert int(by_type["type_b"]["queued"]) == 0

    _ = a


def test_requeue_dead_letter_jobs_bulk_requeues_recoverable_jobs(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, max_attempts=1, retry_backoff_seconds=0.01, poll_interval_seconds=0.01)

    def _always_fail(_: dict) -> dict:
        raise RuntimeError("boom")

    service.register_handler("bulk_requeue", _always_fail)
    service.start_worker()

    first = service.submit("bulk_requeue", payload={})
    second = service.submit("bulk_requeue", payload={})

    for _ in range(300):
        first_state = service.get(first.job_id)
        second_state = service.get(second.job_id)
        assert first_state is not None
        assert second_state is not None
        if first_state.status == "dead_letter" and second_state.status == "dead_letter":
            break
        time.sleep(0.01)

    service.register_handler("bulk_requeue", lambda _: {"ok": True})
    affected = service.requeue_dead_letter_jobs(job_type="bulk_requeue", limit=10)
    assert affected >= 2


def test_requeue_dead_letter_jobs_bulk_honors_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, max_attempts=1, retry_backoff_seconds=0.01, poll_interval_seconds=0.01)

    def _always_fail(_: dict) -> dict:
        raise RuntimeError("boom")

    service.register_handler("bulk_requeue_limited", _always_fail)
    service.start_worker()

    first = service.submit("bulk_requeue_limited", payload={})
    second = service.submit("bulk_requeue_limited", payload={})

    for _ in range(300):
        first_state = service.get(first.job_id)
        second_state = service.get(second.job_id)
        assert first_state is not None
        assert second_state is not None
        if first_state.status == "dead_letter" and second_state.status == "dead_letter":
            break
        time.sleep(0.01)

    service.register_handler("bulk_requeue_limited", lambda _: {"ok": True})
    affected = service.requeue_dead_letter_jobs(job_type="bulk_requeue_limited", limit=1)
    assert affected == 1


def test_requeue_dead_letter_jobs_bulk_dry_run_does_not_mutate(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, max_attempts=1, retry_backoff_seconds=0.01, poll_interval_seconds=0.01)

    def _always_fail(_: dict) -> dict:
        raise RuntimeError("boom")

    service.register_handler("bulk_requeue_dry", _always_fail)
    service.start_worker()
    submitted = service.submit("bulk_requeue_dry", payload={})

    for _ in range(300):
        state = service.get(submitted.job_id)
        assert state is not None
        if state.status == "dead_letter":
            break
        time.sleep(0.01)

    service.register_handler("bulk_requeue_dry", lambda _: {"ok": True})
    affected = service.requeue_dead_letter_jobs(job_type="bulk_requeue_dry", limit=10, dry_run=True)
    assert affected == 1

    unchanged = service.get(submitted.job_id)
    assert unchanged is not None
    assert unchanged.status == "dead_letter"
