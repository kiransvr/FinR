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


def test_ensure_worker_alive_starts_when_worker_is_down(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("ensure_job", lambda _: {"ok": True})

    assert service.is_worker_alive() is False
    started = service.ensure_worker_alive()
    assert started is True
    assert service.is_worker_alive() is True


def test_ensure_worker_alive_noop_when_worker_already_alive(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("ensure_job", lambda _: {"ok": True})
    service.start_worker()

    started = service.ensure_worker_alive()
    assert started is False
    assert service.is_worker_alive() is True


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


def test_get_queue_age_status_detects_breach(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("age_job", lambda _: {"ok": True})

    submitted = service.submit("age_job", payload={})
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE job_queue
            SET created_at = '2000-01-01T00:00:00Z'
            WHERE job_id = ?
            """,
            (submitted.job_id,),
        )

    age = service.get_queue_age_status(threshold_seconds=1)
    assert int(age["queued"]) >= 1
    assert bool(age["breached"]) is True
    assert age["oldest_queued_at"] is not None


def test_list_oldest_queued_jobs_returns_oldest_first(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("oldest_job", lambda _: {"ok": True})

    first = service.submit("oldest_job", payload={})
    second = service.submit("oldest_job", payload={})

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE job_queue
            SET created_at = '2000-01-01T00:00:00Z'
            WHERE job_id = ?
            """,
            (first.job_id,),
        )
        conn.execute(
            """
            UPDATE job_queue
            SET created_at = '2001-01-01T00:00:00Z'
            WHERE job_id = ?
            """,
            (second.job_id,),
        )

    rows = service.list_oldest_queued_jobs(limit=2)
    assert len(rows) == 2
    assert rows[0].job_id == first.job_id


def test_get_dead_letter_rate_status_detects_breach(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, max_attempts=1, retry_backoff_seconds=0.01, poll_interval_seconds=0.01)

    def _always_fail(_: dict) -> dict:
        raise RuntimeError("boom")

    service.register_handler("dl_rate", _always_fail)
    service.start_worker()
    service.submit("dl_rate", payload={})

    for _ in range(300):
        stats = service.get_job_stats()
        counts = stats["counts"]
        if int(counts["dead_letter"]) >= 1:
            break
        time.sleep(0.01)

    rate = service.get_dead_letter_rate_status(window_seconds=60, threshold_per_minute=0.01)
    assert int(rate["recent_dead_letter"]) >= 1
    assert bool(rate["breached"]) is True


def test_get_dead_letter_rate_status_no_breach_with_high_threshold(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, max_attempts=1, retry_backoff_seconds=0.01, poll_interval_seconds=0.01)

    def _always_fail(_: dict) -> dict:
        raise RuntimeError("boom")

    service.register_handler("dl_rate", _always_fail)
    service.start_worker()
    service.submit("dl_rate", payload={})

    for _ in range(300):
        stats = service.get_job_stats()
        counts = stats["counts"]
        if int(counts["dead_letter"]) >= 1:
            break
        time.sleep(0.01)

    rate = service.get_dead_letter_rate_status(window_seconds=60, threshold_per_minute=1000)
    assert bool(rate["breached"]) is False


def test_get_dead_letter_top_types_returns_sorted_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path, max_attempts=1, retry_backoff_seconds=0.01, poll_interval_seconds=0.01)

    def _always_fail(_: dict) -> dict:
        raise RuntimeError("boom")

    service.register_handler("dl_hot_a", _always_fail)
    service.register_handler("dl_hot_b", _always_fail)
    service.start_worker()

    service.submit("dl_hot_a", payload={})
    service.submit("dl_hot_a", payload={})
    service.submit("dl_hot_b", payload={})

    for _ in range(400):
        stats = service.get_job_stats()
        counts = stats["counts"]
        if int(counts["dead_letter"]) >= 3:
            break
        time.sleep(0.01)

    rows = service.get_dead_letter_top_types(limit=10)
    assert len(rows) >= 2
    assert str(rows[0]["job_type"]) == "dl_hot_a"
    assert int(rows[0]["dead_letter"]) >= 2


def test_get_dead_letter_error_summary_returns_sorted_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("err_job", lambda _: {"ok": True})

    first = service.submit("err_job", payload={})
    second = service.submit("err_job", payload={})
    third = service.submit("err_job", payload={})

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE job_queue SET status='dead_letter', error='timeout'
            WHERE job_id = ?
            """,
            (first.job_id,),
        )
        conn.execute(
            """
            UPDATE job_queue SET status='dead_letter', error='timeout'
            WHERE job_id = ?
            """,
            (second.job_id,),
        )
        conn.execute(
            """
            UPDATE job_queue SET status='dead_letter', error='validation'
            WHERE job_id = ?
            """,
            (third.job_id,),
        )

    rows = service.get_dead_letter_error_summary(limit=10)
    assert len(rows) >= 2
    assert str(rows[0]["error_message"]) == "timeout"
    assert int(rows[0]["dead_letter"]) == 2


def test_list_recent_dead_letter_jobs_returns_newest_first(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("recent_dl", lambda _: {"ok": True})

    first = service.submit("recent_dl", payload={})
    second = service.submit("recent_dl", payload={})

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE job_queue SET status='dead_letter', error='first', updated_at='2000-01-01T00:00:00Z'
            WHERE job_id = ?
            """,
            (first.job_id,),
        )
        conn.execute(
            """
            UPDATE job_queue SET status='dead_letter', error='second', updated_at='2001-01-01T00:00:00Z'
            WHERE job_id = ?
            """,
            (second.job_id,),
        )

    rows = service.list_recent_dead_letter_jobs(limit=10)
    assert len(rows) >= 2
    assert rows[0].job_id == second.job_id
    assert rows[1].job_id == first.job_id


def test_get_dead_letter_trend_status_detects_upward_direction(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("trend_job", lambda _: {"ok": True})

    older = service.submit("trend_job", payload={})
    recent_a = service.submit("trend_job", payload={})
    recent_b = service.submit("trend_job", payload={})

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE job_queue SET status='dead_letter', updated_at='2000-01-01T00:00:00Z'
            WHERE job_id = ?
            """,
            (older.job_id,),
        )
        conn.execute(
            """
            UPDATE job_queue SET status='dead_letter', updated_at='2099-01-01T00:00:00Z'
            WHERE job_id = ?
            """,
            (recent_a.job_id,),
        )
        conn.execute(
            """
            UPDATE job_queue SET status='dead_letter', updated_at='2099-01-01T00:00:00Z'
            WHERE job_id = ?
            """,
            (recent_b.job_id,),
        )

    trend = service.get_dead_letter_trend_status(window_seconds=3600)
    assert int(trend["recent_count"]) == 2
    assert int(trend["previous_count"]) == 0
    assert int(trend["delta"]) == 2
    assert str(trend["direction"]) == "up"


def test_get_alert_signals_status_reports_warning_on_queue_age_breach(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 1,
        "drained": False,
    }

    submitted = service.submit("signals_job", payload={})
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET created_at = '2000-01-01T00:00:00Z'
                WHERE job_id = ?
                """,
                (submitted.job_id,),
            )

        status = service.get_alert_signals_status(
            queue_age_threshold_seconds=1,
            dead_letter_window_seconds=60,
            dead_letter_threshold_per_minute=1000,
        )
        assert str(status["severity"]) == "warning"
        assert bool(status["breached"]) is True
        signals = status["signals"]
        assert isinstance(signals, list)
        queue_signal = next((item for item in signals if str(item["name"]) == "queue_age"), None)
        assert queue_signal is not None
        assert bool(queue_signal["breached"]) is True
        assert str(queue_signal["status"]) == "warning"
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_alert_signals_status_reports_critical_when_worker_is_down(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    status = service.get_alert_signals_status(
        queue_age_threshold_seconds=300,
        dead_letter_window_seconds=60,
        dead_letter_threshold_per_minute=1000,
    )
    assert str(status["severity"]) == "critical"
    assert bool(status["breached"]) is True
    signals = status["signals"]
    assert isinstance(signals, list)
    worker_signal = next((item for item in signals if str(item["name"]) == "worker"), None)
    assert worker_signal is not None
    assert bool(worker_signal["breached"]) is True
    assert str(worker_signal["status"]) == "critical"


def test_get_failing_alert_signals_returns_only_breached_with_recommendations(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 1,
        "drained": False,
    }

    submitted = service.submit("signals_job", payload={})
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET created_at = '2000-01-01T00:00:00Z'
                WHERE job_id = ?
                """,
                (submitted.job_id,),
            )

        failing = service.get_failing_alert_signals(
            queue_age_threshold_seconds=1,
            dead_letter_window_seconds=60,
            dead_letter_threshold_per_minute=1000,
        )
        assert str(failing["severity"]) == "warning"
        assert bool(failing["breached"]) is True
        assert int(failing["total_signals"]) == 3
        assert int(failing["failing_count"]) == 1
        rows = failing["signals"]
        assert isinstance(rows, list)
        assert len(rows) == 1
        assert str(rows[0]["name"]) == "queue_age"
        assert isinstance(rows[0]["recommendation"], str)
        assert rows[0]["recommendation"]
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_failing_alert_signals_empty_when_all_ok(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }

    try:
        failing = service.get_failing_alert_signals(
            queue_age_threshold_seconds=300,
            dead_letter_window_seconds=60,
            dead_letter_threshold_per_minute=1000,
        )
        assert str(failing["severity"]) == "ok"
        assert bool(failing["breached"]) is False
        assert int(failing["failing_count"]) == 0
        assert failing["signals"] == []
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_alert_gate_status_warning_passes_in_relaxed_mode(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 1,
        "drained": False,
    }

    submitted = service.submit("signals_job", payload={})
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET created_at = '2000-01-01T00:00:00Z'
                WHERE job_id = ?
                """,
                (submitted.job_id,),
            )

        relaxed = service.get_alert_gate_status(
            queue_age_threshold_seconds=1,
            dead_letter_window_seconds=60,
            dead_letter_threshold_per_minute=1000,
            fail_on_warning=False,
        )
        strict = service.get_alert_gate_status(
            queue_age_threshold_seconds=1,
            dead_letter_window_seconds=60,
            dead_letter_threshold_per_minute=1000,
            fail_on_warning=True,
        )

        assert str(relaxed["severity"]) == "warning"
        assert bool(relaxed["pass_gate"]) is True
        assert bool(strict["pass_gate"]) is False
        reasons = relaxed["reasons"]
        assert isinstance(reasons, list)
        assert len(reasons) >= 1
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_alert_gate_status_critical_fails_even_in_relaxed_mode(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    gate = service.get_alert_gate_status(
        queue_age_threshold_seconds=300,
        dead_letter_window_seconds=60,
        dead_letter_threshold_per_minute=1000,
        fail_on_warning=False,
    )
    assert str(gate["severity"]) == "critical"
    assert bool(gate["pass_gate"]) is False
    assert int(gate["failing_count"]) >= 1


def test_get_alert_gate_matrix_status_reports_relaxed_and_strict_modes(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 1,
        "drained": False,
    }

    submitted = service.submit("signals_job", payload={})
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET created_at = '2000-01-01T00:00:00Z'
                WHERE job_id = ?
                """,
                (submitted.job_id,),
            )

        matrix = service.get_alert_gate_matrix_status(
            queue_age_threshold_seconds=1,
            dead_letter_window_seconds=60,
            dead_letter_threshold_per_minute=1000,
        )
        assert str(matrix["severity"]) == "warning"
        assert bool(matrix["breached"]) is True

        relaxed = matrix["relaxed"]
        strict = matrix["strict"]
        assert bool(relaxed["pass_gate"]) is True
        assert bool(strict["pass_gate"]) is False
        assert int(relaxed["recommended_status_code"]) == 200
        assert int(strict["recommended_status_code"]) == 503
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_alert_gate_matrix_status_critical_fails_both_modes(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    matrix = service.get_alert_gate_matrix_status(
        queue_age_threshold_seconds=300,
        dead_letter_window_seconds=60,
        dead_letter_threshold_per_minute=1000,
    )
    assert str(matrix["severity"]) == "critical"
    relaxed = matrix["relaxed"]
    strict = matrix["strict"]
    assert bool(relaxed["pass_gate"]) is False
    assert bool(strict["pass_gate"]) is False


def test_get_alert_gate_policy_advice_prefers_relaxed_on_warning(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 1,
        "drained": False,
    }

    submitted = service.submit("signals_job", payload={})
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET created_at = '2000-01-01T00:00:00Z'
                WHERE job_id = ?
                """,
                (submitted.job_id,),
            )

        advice = service.get_alert_gate_policy_advice(
            queue_age_threshold_seconds=1,
            dead_letter_window_seconds=60,
            dead_letter_threshold_per_minute=1000,
        )
        assert str(advice["severity"]) == "warning"
        assert bool(advice["relaxed_pass"]) is True
        assert bool(advice["strict_pass"]) is False
        assert str(advice["recommended_mode"]) == "relaxed"
        assert bool(advice["deployment_allowed"]) is True
        assert int(advice["recommended_status_code"]) == 200
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_alert_gate_policy_advice_prefers_strict_when_all_ok(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 0,
        "drained": True,
    }

    try:
        advice = service.get_alert_gate_policy_advice(
            queue_age_threshold_seconds=300,
            dead_letter_window_seconds=60,
            dead_letter_threshold_per_minute=1000,
        )
        assert str(advice["severity"]) == "ok"
        assert bool(advice["relaxed_pass"]) is True
        assert bool(advice["strict_pass"]) is True
        assert str(advice["recommended_mode"]) == "strict"
        assert bool(advice["deployment_allowed"]) is True
        assert int(advice["recommended_status_code"]) == 200
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_alert_gate_policy_advice_blocks_on_critical(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    advice = service.get_alert_gate_policy_advice(
        queue_age_threshold_seconds=300,
        dead_letter_window_seconds=60,
        dead_letter_threshold_per_minute=1000,
    )
    assert str(advice["severity"]) == "critical"
    assert bool(advice["relaxed_pass"]) is False
    assert bool(advice["strict_pass"]) is False
    assert str(advice["recommended_mode"]) == "block"
    assert bool(advice["deployment_allowed"]) is False
    assert int(advice["recommended_status_code"]) == 503


def test_get_alert_gate_evaluation_mode_split_on_warning(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 1,
        "drained": False,
    }

    submitted = service.submit("signals_job", payload={})
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET created_at = '2000-01-01T00:00:00Z'
                WHERE job_id = ?
                """,
                (submitted.job_id,),
            )

        strict_eval = service.get_alert_gate_evaluation(
            mode="strict",
            queue_age_threshold_seconds=1,
            dead_letter_window_seconds=60,
            dead_letter_threshold_per_minute=1000,
        )
        relaxed_eval = service.get_alert_gate_evaluation(
            mode="relaxed",
            queue_age_threshold_seconds=1,
            dead_letter_window_seconds=60,
            dead_letter_threshold_per_minute=1000,
        )
        advice_eval = service.get_alert_gate_evaluation(
            mode="advice",
            queue_age_threshold_seconds=1,
            dead_letter_window_seconds=60,
            dead_letter_threshold_per_minute=1000,
        )

        assert bool(strict_eval["pass_gate"]) is False
        assert bool(relaxed_eval["pass_gate"]) is True
        assert bool(advice_eval["pass_gate"]) is True
        assert str(advice_eval["recommended_mode"]) == "relaxed"
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_alert_gate_evaluation_rejects_invalid_mode(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    try:
        _ = service.get_alert_gate_evaluation(mode="invalid")
        raise AssertionError("Expected ValueError for invalid mode")
    except ValueError:
        pass


def test_get_alert_gate_profile_evaluation_maps_profiles_to_modes(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 1,
        "drained": False,
    }

    submitted = service.submit("signals_job", payload={})
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET created_at = '2000-01-01T00:00:00Z'
                WHERE job_id = ?
                """,
                (submitted.job_id,),
            )

        prod_eval = service.get_alert_gate_profile_evaluation(profile="prod", queue_age_threshold_seconds=1)
        staging_eval = service.get_alert_gate_profile_evaluation(profile="staging", queue_age_threshold_seconds=1)
        dev_eval = service.get_alert_gate_profile_evaluation(profile="dev", queue_age_threshold_seconds=1)

        assert str(prod_eval["profile_mode"]) == "strict"
        assert str(staging_eval["profile_mode"]) == "advice"
        assert str(dev_eval["profile_mode"]) == "relaxed"
        assert bool(prod_eval["pass_gate"]) is False
        assert bool(staging_eval["pass_gate"]) is True
        assert bool(dev_eval["pass_gate"]) is True
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_alert_gate_profile_evaluation_rejects_invalid_profile(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    try:
        _ = service.get_alert_gate_profile_evaluation(profile="qa")
        raise AssertionError("Expected ValueError for invalid profile")
    except ValueError:
        pass


def test_get_alert_gate_profile_matrix_evaluation_recommends_best_profile(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 1,
        "drained": False,
    }

    submitted = service.submit("signals_job", payload={})
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET created_at = '2000-01-01T00:00:00Z'
                WHERE job_id = ?
                """,
                (submitted.job_id,),
            )

        matrix = service.get_alert_gate_profile_matrix_evaluation(queue_age_threshold_seconds=1)
        assert str(matrix["recommended_profile"]) == "staging"
        assert bool(matrix["deployment_allowed"]) is True
        profiles = matrix["profiles"]
        assert isinstance(profiles, dict)
        assert bool(profiles["prod"]["pass_gate"]) is False
        assert bool(profiles["staging"]["pass_gate"]) is True
        assert bool(profiles["dev"]["pass_gate"]) is True
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_alert_gate_profile_rollout_recommendation_prefers_staging_on_warning(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 1,
        "drained": False,
    }

    submitted = service.submit("signals_job", payload={})
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET created_at = '2000-01-01T00:00:00Z'
                WHERE job_id = ?
                """,
                (submitted.job_id,),
            )

        rollout = service.get_alert_gate_profile_rollout_recommendation(queue_age_threshold_seconds=1)
        assert str(rollout["recommended_profile"]) == "staging"
        assert str(rollout["recommended_action"]) == "hold_in_staging"
        assert str(rollout["next_profile"]) == "staging"
        assert bool(rollout["deployment_allowed"]) is True
        assert int(rollout["recommended_status_code"]) == 200
        assert isinstance(rollout["reasons"], list)
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_alert_gate_profile_rollout_recommendation_blocks_when_worker_down(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    rollout = service.get_alert_gate_profile_rollout_recommendation()
    assert str(rollout["recommended_profile"]) == "block"
    assert str(rollout["recommended_action"]) == "block_release"
    assert rollout["next_profile"] is None
    assert bool(rollout["deployment_allowed"]) is False
    assert int(rollout["recommended_status_code"]) == 503
    assert isinstance(rollout["reasons"], list)


def test_get_alert_gate_profile_rollout_plan_prefers_staging_on_warning(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 1,
        "drained": False,
    }

    submitted = service.submit("signals_job", payload={})
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET created_at = '2000-01-01T00:00:00Z'
                WHERE job_id = ?
                """,
                (submitted.job_id,),
            )

        plan = service.get_alert_gate_profile_rollout_plan(queue_age_threshold_seconds=1)
        assert str(plan["recommended_profile"]) == "staging"
        assert str(plan["recommended_action"]) == "hold_in_staging"
        assert plan["promotion_path"] == ["dev", "staging"]
        blocking_profiles = plan["blocking_profiles"]
        assert isinstance(blocking_profiles, list)
        assert "prod" in blocking_profiles
        stages = plan["stages"]
        assert isinstance(stages, list)
        assert len(stages) == 3
        assert str(stages[0]["profile"]) == "dev"
        assert str(stages[1]["profile"]) == "staging"
        assert str(stages[2]["profile"]) == "prod"
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_alert_gate_profile_rollout_plan_blocks_when_worker_down(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    plan = service.get_alert_gate_profile_rollout_plan()
    assert str(plan["recommended_profile"]) == "block"
    assert str(plan["recommended_action"]) == "block_release"
    assert plan["promotion_path"] == []
    assert plan["next_profile"] is None
    assert bool(plan["deployment_allowed"]) is False


def test_get_alert_gate_profile_rollout_summary_prefers_staging_on_warning(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 1,
        "drained": False,
    }

    submitted = service.submit("signals_job", payload={})
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET created_at = '2000-01-01T00:00:00Z'
                WHERE job_id = ?
                """,
                (submitted.job_id,),
            )

        summary = service.get_alert_gate_profile_rollout_summary(queue_age_threshold_seconds=1)
        assert str(summary["recommended_profile"]) == "staging"
        assert str(summary["recommended_action"]) == "hold_in_staging"
        assert str(summary["release_readiness"]) == "ready_for_staging"
        assert str(summary["highest_eligible_profile"]) == "staging"
        assert int(summary["eligible_stages"]) == 2
        assert int(summary["blocked_stages"]) == 1
        assert int(summary["total_stages"]) == 3
        assert bool(summary["suppression_active"]) is False
        assert bool(summary["suppressed"]) is False
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_alert_gate_profile_rollout_summary_is_blocked_when_worker_down(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    summary = service.get_alert_gate_profile_rollout_summary()
    assert str(summary["recommended_profile"]) == "block"
    assert str(summary["recommended_action"]) == "block_release"
    assert str(summary["release_readiness"]) == "blocked"
    assert summary["highest_eligible_profile"] is None
    assert int(summary["eligible_stages"]) == 0
    assert int(summary["blocked_stages"]) == 3
    assert int(summary["total_stages"]) == 3


def test_get_alert_gate_profile_rollout_summary_marks_warning_as_suppressed_when_window_active(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    original_get_worker_status = service.get_worker_status
    service.get_worker_status = lambda: {
        "worker_alive": True,
        "paused": False,
        "running": 0,
        "queued": 1,
        "drained": False,
    }

    submitted = service.submit("signals_job", payload={})
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET created_at = '2000-01-01T00:00:00Z'
                WHERE job_id = ?
                """,
                (submitted.job_id,),
            )

        summary = service.get_alert_gate_profile_rollout_summary(
            queue_age_threshold_seconds=1,
            suppress_warning_until="2999-01-01T00:00:00Z",
            suppression_reason="maintenance-window",
        )
        assert str(summary["severity"]) == "warning"
        assert bool(summary["deployment_allowed"]) is True
        assert int(summary["recommended_status_code"]) == 200
        assert bool(summary["suppression_active"]) is True
        assert bool(summary["suppressed"]) is True
    finally:
        service.get_worker_status = original_get_worker_status


def test_get_alert_gate_profile_rollout_summary_does_not_suppress_critical(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    summary = service.get_alert_gate_profile_rollout_summary(
        suppress_warning_until="2999-01-01T00:00:00Z",
        suppression_reason="maintenance-window",
    )
    assert str(summary["severity"]) == "critical"
    assert bool(summary["deployment_allowed"]) is False
    assert int(summary["recommended_status_code"]) == 503
    assert bool(summary["suppression_active"]) is True
    assert bool(summary["suppressed"]) is False


def test_get_alert_gate_profile_rollout_policy_returns_thresholds(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    payload = service.get_alert_gate_profile_rollout_policy(policy="strict-prod")
    assert str(payload["policy"]) == "strict-prod"
    assert float(payload["queue_age_threshold_seconds"]) == 120.0
    assert float(payload["dead_letter_window_seconds"]) == 1800.0
    assert float(payload["dead_letter_threshold_per_minute"]) == 0.2
    assert str(payload["release_readiness"]) in {
        "ready_for_prod",
        "ready_for_staging",
        "dev_only",
        "blocked",
    }


def test_get_alert_gate_profile_rollout_policy_rejects_invalid_value(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)
    service.register_handler("signals_job", lambda _: {"ok": True})

    try:
        _ = service.get_alert_gate_profile_rollout_policy(policy="legacy")
        raise AssertionError("Expected ValueError for invalid policy")
    except ValueError:
        pass


def test_add_alert_incident_annotation_and_list_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)

    created = service.add_alert_incident_annotation(
        summary="Suppressed warning during maintenance",
        scope="rollout",
        details={"ticket": "OPS-123"},
        created_by="admin",
        created_by_role="admin",
    )
    assert str(created["scope"]) == "rollout"
    assert str(created["summary"]) == "Suppressed warning during maintenance"

    rows = service.list_alert_incident_annotations(limit=10)
    assert len(rows) >= 1
    latest = rows[0]
    assert str(latest["annotation_id"]) == str(created["annotation_id"])
    assert str(latest["created_by"]) == "admin"
    assert isinstance(latest["details"], dict)


def test_list_alert_incident_annotations_supports_scope_filter(tmp_path: Path) -> None:
    db_path = tmp_path / "job_queue.db"
    service = JobService(db_path=db_path)

    service.add_alert_incident_annotation(
        summary="Rollout note",
        scope="rollout",
        details={},
        created_by="admin",
        created_by_role="admin",
    )
    service.add_alert_incident_annotation(
        summary="Canary note",
        scope="canary",
        details={},
        created_by="admin",
        created_by_role="admin",
    )

    rollout_rows = service.list_alert_incident_annotations(limit=10, scope="rollout")
    assert len(rollout_rows) >= 1
    assert all(str(item["scope"]) == "rollout" for item in rollout_rows)


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
