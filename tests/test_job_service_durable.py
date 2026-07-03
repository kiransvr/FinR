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
        if final_status in {"succeeded", "failed"}:
            break
        time.sleep(0.01)

    assert final_status == "succeeded"

    reloaded = JobService(db_path=db_path, poll_interval_seconds=0.01)
    loaded = reloaded.get(submitted.job_id)
    assert loaded is not None
    assert loaded.status == "succeeded"
    assert loaded.result == {"echo": "ok"}
