from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
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
    """Runs background jobs and tracks lifecycle in an in-memory registry."""

    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="risk-jobs")
        self._jobs: dict[str, JobState] = {}
        self._lock = Lock()

    def submit(self, job_type: str, runner: Callable[[], dict]) -> JobState:
        now = self._utc_now()
        job_id = str(uuid4())
        state = JobState(
            job_id=job_id,
            job_type=job_type,
            status="queued",
            created_at=now,
            updated_at=now,
            result=None,
            error=None,
        )
        with self._lock:
            self._jobs[job_id] = state

        self._executor.submit(self._run_job, job_id, runner)
        return state

    def get(self, job_id: str) -> JobState | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _run_job(self, job_id: str, runner: Callable[[], dict]) -> None:
        self._update(job_id, status="running")
        try:
            result = runner()
            self._update(job_id, status="succeeded", result=result, error=None)
        except Exception as exc:  # pragma: no cover - defensive guard
            self._update(job_id, status="failed", result=None, error=str(exc))

    def _update(self, job_id: str, status: str, result: dict | None = None, error: str | None = None) -> None:
        with self._lock:
            current = self._jobs[job_id]
            self._jobs[job_id] = JobState(
                job_id=current.job_id,
                job_type=current.job_type,
                status=status,
                created_at=current.created_at,
                updated_at=self._utc_now(),
                result=result,
                error=error,
            )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
