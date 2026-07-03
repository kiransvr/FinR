from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from threading import Event, Lock, Thread
import time
from typing import Callable
from uuid import uuid4


@dataclass(frozen=True)
class JobState:
    job_id: str
    job_type: str
    status: str
    created_at: str
    updated_at: str
    attempts: int = 0
    max_attempts: int = 0
    timeout_seconds: float = 0.0
    result: dict | None = None
    error: str | None = None


class JobService:
    """Runs background jobs with durable SQLite-backed queue state."""

    def __init__(
        self,
        db_path: Path,
        poll_interval_seconds: float = 0.2,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 0.2,
        default_timeout_seconds: float = 60.0,
        running_stale_seconds: float = 300.0,
    ):
        self._db_path = db_path
        self._poll_interval_seconds = poll_interval_seconds
        self._default_max_attempts = max(1, max_attempts)
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self._default_timeout_seconds = max(0.01, default_timeout_seconds)
        self._running_stale_seconds = max(1.0, running_stale_seconds)
        self._handlers: dict[str, Callable[[dict], dict]] = {}
        self._runner_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="risk-job-runner")
        self._lock = Lock()
        self._stop_event = Event()
        self._worker: Thread | None = None
        self._ensure_schema()

    def register_handler(self, job_type: str, runner: Callable[[dict], dict]) -> None:
        self._handlers[job_type] = runner

    def start_worker(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._worker = Thread(target=self._worker_loop, name="risk-job-worker", daemon=True)
        self._worker.start()

    def submit(
        self,
        job_type: str,
        payload: dict | None = None,
        max_attempts: int | None = None,
        timeout_seconds: float | None = None,
    ) -> JobState:
        if job_type not in self._handlers:
            raise ValueError(f"No handler registered for job_type '{job_type}'")

        now = self._utc_now()
        job_id = str(uuid4())
        payload_json = json.dumps(payload or {})
        resolved_max_attempts = max(1, max_attempts or self._default_max_attempts)
        resolved_timeout_seconds = max(0.01, timeout_seconds or self._default_timeout_seconds)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO job_queue(
                    job_id, job_type, status, payload_json, result_json, error,
                    attempts, max_attempts, timeout_seconds, next_attempt_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    job_type,
                    "queued",
                    payload_json,
                    0,
                    resolved_max_attempts,
                    resolved_timeout_seconds,
                    now,
                    now,
                    now,
                ),
            )

        return JobState(
            job_id=job_id,
            job_type=job_type,
            status="queued",
            created_at=now,
            updated_at=now,
            attempts=0,
            max_attempts=resolved_max_attempts,
            timeout_seconds=resolved_timeout_seconds,
        )

    def submit_deduplicated(
        self,
        job_type: str,
        payload: dict | None = None,
        max_attempts: int | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[JobState, bool]:
        if job_type not in self._handlers:
            raise ValueError(f"No handler registered for job_type '{job_type}'")

        with self._lock:
            with self._connect() as conn:
                existing = conn.execute(
                    """
                    SELECT job_id, job_type, status, result_json, error, created_at, updated_at, attempts, max_attempts, timeout_seconds
                    FROM job_queue
                    WHERE job_type = ?
                      AND status IN ('queued', 'running')
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (job_type,),
                ).fetchone()
                if existing is not None:
                    return self._row_to_state(existing), False

        return self.submit(
            job_type=job_type,
            payload=payload,
            max_attempts=max_attempts,
            timeout_seconds=timeout_seconds,
        ), True

    def get(self, job_id: str) -> JobState | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, job_type, status, result_json, error, created_at, updated_at, attempts, max_attempts, timeout_seconds
                FROM job_queue
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_state(row)

    def list_jobs(self, status_filter: str | None = None, limit: int = 50) -> list[JobState]:
        capped_limit = max(1, min(200, int(limit)))
        with self._connect() as conn:
            if status_filter:
                rows = conn.execute(
                    """
                    SELECT job_id, job_type, status, result_json, error, created_at, updated_at, attempts, max_attempts, timeout_seconds
                    FROM job_queue
                    WHERE status = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (status_filter.strip().lower(), capped_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT job_id, job_type, status, result_json, error, created_at, updated_at, attempts, max_attempts, timeout_seconds
                    FROM job_queue
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (capped_limit,),
                ).fetchall()

        return [self._row_to_state(row) for row in rows]

    def get_job_stats(self) -> dict[str, object]:
        with self._connect() as conn:
            count_rows = conn.execute(
                """
                SELECT status, COUNT(*)
                FROM job_queue
                GROUP BY status
                """
            ).fetchall()
            oldest_rows = conn.execute(
                """
                SELECT status, MIN(created_at)
                FROM job_queue
                WHERE status IN ('queued', 'running', 'dead_letter')
                GROUP BY status
                """
            ).fetchall()

        counts = {str(row[0]): int(row[1]) for row in count_rows}
        oldest = {str(row[0]): str(row[1]) for row in oldest_rows if row[1]}
        return {
            "counts": {
                "queued": counts.get("queued", 0),
                "running": counts.get("running", 0),
                "succeeded": counts.get("succeeded", 0),
                "dead_letter": counts.get("dead_letter", 0),
                "canceled": counts.get("canceled", 0),
                "total": sum(counts.values()),
            },
            "oldest": {
                "queued": oldest.get("queued"),
                "running": oldest.get("running"),
                "dead_letter": oldest.get("dead_letter"),
            },
        }

    def requeue_dead_letter(self, job_id: str) -> JobState | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT job_type, status
                    FROM job_queue
                    WHERE job_id = ?
                    """,
                    (job_id,),
                ).fetchone()

                if row is None:
                    return None

                job_type = str(row[0])
                status = str(row[1])
                if status != "dead_letter":
                    raise ValueError("Only dead-letter jobs can be requeued")
                if job_type not in self._handlers:
                    raise ValueError(f"No handler registered for job_type '{job_type}'")

                now = self._utc_now()
                conn.execute(
                    """
                    UPDATE job_queue
                    SET status = ?, attempts = 0, result_json = NULL, error = NULL, next_attempt_at = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    ("queued", now, now, job_id),
                )

        return self.get(job_id)

    def cancel_queued_job(self, job_id: str) -> JobState | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT status
                    FROM job_queue
                    WHERE job_id = ?
                    """,
                    (job_id,),
                ).fetchone()

                if row is None:
                    return None

                status = str(row[0])
                if status != "queued":
                    raise ValueError("Only queued jobs can be canceled")

                now = self._utc_now()
                conn.execute(
                    """
                    UPDATE job_queue
                    SET status = ?, next_attempt_at = NULL, updated_at = ?
                    WHERE job_id = ?
                    """,
                    ("canceled", now, job_id),
                )

        return self.get(job_id)

    def cleanup_terminal_jobs(self, older_than_seconds: float = 86400.0) -> int:
        cutoff_seconds = max(0.0, older_than_seconds)
        cutoff = self._utc_now_plus_seconds(-cutoff_seconds)
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM job_queue
                    WHERE status IN ('succeeded', 'dead_letter', 'canceled')
                      AND updated_at <= ?
                    """,
                    (cutoff,),
                )
                return max(0, int(cursor.rowcount))

    def recover_stale_running_jobs(self, stale_after_seconds: float | None = None) -> int:
        stale_seconds = max(1.0, stale_after_seconds or self._running_stale_seconds)
        cutoff = self._utc_now_plus_seconds(-stale_seconds)
        now = self._utc_now()
        recovered = 0

        with self._lock:
            with self._connect() as conn:
                stale_rows = conn.execute(
                    """
                    SELECT job_id, attempts, max_attempts
                    FROM job_queue
                    WHERE status = 'running'
                      AND updated_at <= ?
                    """,
                    (cutoff,),
                ).fetchall()

                for row in stale_rows:
                    job_id = str(row[0])
                    attempts = int(row[1])
                    max_attempts = int(row[2])
                    if attempts < max_attempts:
                        conn.execute(
                            """
                            UPDATE job_queue
                            SET status = ?, error = ?, next_attempt_at = ?, updated_at = ?
                            WHERE job_id = ?
                            """,
                            (
                                "queued",
                                "Recovered stale running job; requeued",
                                now,
                                now,
                                job_id,
                            ),
                        )
                    else:
                        conn.execute(
                            """
                            UPDATE job_queue
                            SET status = ?, error = ?, next_attempt_at = NULL, updated_at = ?
                            WHERE job_id = ?
                            """,
                            (
                                "dead_letter",
                                "Recovered stale running job exceeded max attempts",
                                now,
                                job_id,
                            ),
                        )
                    recovered += 1

        return recovered

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            self.recover_stale_running_jobs()
            claimed = self._claim_next_queued_job()
            if not claimed:
                time.sleep(self._poll_interval_seconds)
                continue

            job_id, job_type, payload_json, attempts, max_attempts, timeout_seconds = claimed
            runner = self._handlers.get(job_type)
            if runner is None:
                self._finish_failed(
                    job_id,
                    error=f"No handler registered for job_type '{job_type}'",
                    attempts=attempts,
                    max_attempts=max_attempts,
                )
                continue

            payload: dict = json.loads(payload_json) if payload_json else {}
            try:
                result = self._execute_with_timeout(runner, payload, timeout_seconds)
                self._finish_succeeded(job_id, result)
            except Exception as exc:  # pragma: no cover - defensive guard
                self._finish_failed(job_id, error=str(exc), attempts=attempts, max_attempts=max_attempts)

    def _claim_next_queued_job(self) -> tuple[str, str, str, int, int, float] | None:
        now = self._utc_now()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT job_id, job_type, payload_json, attempts, max_attempts, timeout_seconds
                    FROM job_queue
                    WHERE status = 'queued'
                      AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                    ORDER BY next_attempt_at ASC, created_at ASC
                    LIMIT 1
                    """,
                    (now,),
                ).fetchone()
                if row is None:
                    return None

                next_attempt_number = int(row[3]) + 1
                conn.execute(
                    """
                    UPDATE job_queue
                    SET status = ?, attempts = ?, updated_at = ?
                    WHERE job_id = ? AND status = 'queued'
                    """,
                    ("running", next_attempt_number, now, row[0]),
                )

            return row[0], row[1], row[2] or "{}", next_attempt_number, int(row[4]), float(row[5])

    def _finish_succeeded(self, job_id: str, result: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET status = ?, result_json = ?, error = NULL, next_attempt_at = NULL, updated_at = ?
                WHERE job_id = ?
                """,
                ("succeeded", json.dumps(result), self._utc_now(), job_id),
            )

    def _finish_failed(self, job_id: str, error: str, attempts: int, max_attempts: int) -> None:
        now = self._utc_now()
        if attempts < max_attempts:
            retry_at = self._utc_now_plus_seconds(self._retry_backoff_seconds * attempts)
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE job_queue
                    SET status = ?, result_json = NULL, error = ?, next_attempt_at = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    ("queued", error, retry_at, now, job_id),
                )
            return

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET status = ?, result_json = NULL, error = ?, next_attempt_at = NULL, updated_at = ?
                WHERE job_id = ?
                """,
                ("dead_letter", error, now, job_id),
            )

    def _ensure_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_queue (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT,
                    result_json TEXT,
                    error TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    timeout_seconds REAL NOT NULL DEFAULT 60,
                    next_attempt_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(job_queue)").fetchall()}
            if "attempts" not in columns:
                conn.execute("ALTER TABLE job_queue ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
            if "max_attempts" not in columns:
                conn.execute("ALTER TABLE job_queue ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3")
            if "timeout_seconds" not in columns:
                conn.execute("ALTER TABLE job_queue ADD COLUMN timeout_seconds REAL NOT NULL DEFAULT 60")
            if "next_attempt_at" not in columns:
                conn.execute("ALTER TABLE job_queue ADD COLUMN next_attempt_at TEXT")

    def _execute_with_timeout(self, runner: Callable[[dict], dict], payload: dict, timeout_seconds: float) -> dict:
        future = self._runner_executor.submit(runner, payload)
        try:
            return future.result(timeout=max(0.01, timeout_seconds))
        except FutureTimeoutError as exc:
            raise TimeoutError(f"Job timed out after {timeout_seconds:.2f}s") from exc

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @staticmethod
    def _row_to_state(row: tuple) -> JobState:
        result: dict | None = json.loads(row[3]) if row[3] else None
        return JobState(
            job_id=row[0],
            job_type=row[1],
            status=row[2],
            attempts=int(row[7]),
            max_attempts=int(row[8]),
            timeout_seconds=float(row[9]),
            result=result,
            error=row[4],
            created_at=row[5],
            updated_at=row[6],
        )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _utc_now_plus_seconds(seconds: float) -> str:
        return (datetime.now(UTC) + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
