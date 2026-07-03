from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
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
    result: dict | None = None
    error: str | None = None


class JobService:
    """Runs background jobs with durable SQLite-backed queue state."""

    def __init__(self, db_path: Path, poll_interval_seconds: float = 0.2):
        self._db_path = db_path
        self._poll_interval_seconds = poll_interval_seconds
        self._handlers: dict[str, Callable[[dict], dict]] = {}
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

    def submit(self, job_type: str, payload: dict | None = None) -> JobState:
        if job_type not in self._handlers:
            raise ValueError(f"No handler registered for job_type '{job_type}'")

        now = self._utc_now()
        job_id = str(uuid4())
        payload_json = json.dumps(payload or {})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO job_queue(job_id, job_type, status, payload_json, result_json, error, created_at, updated_at)
                VALUES (?, ?, ?, ?, NULL, NULL, ?, ?)
                """,
                (job_id, job_type, "queued", payload_json, now, now),
            )

        return JobState(job_id=job_id, job_type=job_type, status="queued", created_at=now, updated_at=now)

    def get(self, job_id: str) -> JobState | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, job_type, status, result_json, error, created_at, updated_at
                FROM job_queue
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            return None

        result: dict | None = json.loads(row[3]) if row[3] else None
        return JobState(
            job_id=row[0],
            job_type=row[1],
            status=row[2],
            result=result,
            error=row[4],
            created_at=row[5],
            updated_at=row[6],
        )

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            claimed = self._claim_next_queued_job()
            if not claimed:
                time.sleep(self._poll_interval_seconds)
                continue

            job_id, job_type, payload_json = claimed
            runner = self._handlers.get(job_type)
            if runner is None:
                self._finish_failed(job_id, f"No handler registered for job_type '{job_type}'")
                continue

            payload: dict = json.loads(payload_json) if payload_json else {}
            try:
                result = runner(payload)
                self._finish_succeeded(job_id, result)
            except Exception as exc:  # pragma: no cover - defensive guard
                self._finish_failed(job_id, str(exc))

    def _claim_next_queued_job(self) -> tuple[str, str, str] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT job_id, job_type, payload_json
                    FROM job_queue
                    WHERE status = 'queued'
                    ORDER BY created_at ASC
                    LIMIT 1
                    """
                ).fetchone()
                if row is None:
                    return None

                conn.execute(
                    """
                    UPDATE job_queue
                    SET status = ?, updated_at = ?
                    WHERE job_id = ? AND status = 'queued'
                    """,
                    ("running", self._utc_now(), row[0]),
                )

            return row[0], row[1], row[2] or "{}"

    def _finish_succeeded(self, job_id: str, result: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET status = ?, result_json = ?, error = NULL, updated_at = ?
                WHERE job_id = ?
                """,
                ("succeeded", json.dumps(result), self._utc_now(), job_id),
            )

    def _finish_failed(self, job_id: str, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE job_queue
                SET status = ?, result_json = NULL, error = ?, updated_at = ?
                WHERE job_id = ?
                """,
                ("failed", error, self._utc_now(), job_id),
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
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
