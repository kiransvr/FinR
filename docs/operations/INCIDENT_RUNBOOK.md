# Incident Runbook

## Purpose

Provide a repeatable response process for production incidents affecting API availability, scoring correctness, authentication, and data pipeline outputs.

## Severity Levels

- SEV-1: Full outage, auth failure for all users, or corrupted scoring outputs affecting decisions.
- SEV-2: Major degradation (high error rate, severe latency, partial endpoint failure).
- SEV-3: Minor degradation with workaround.

## Roles

- Incident Commander: Coordinates triage and communication.
- Ops Engineer: Handles infra/runtime checks and rollback.
- Backend Engineer: Investigates API/service defects.
- Data Engineer: Validates pipeline artifacts and scoring integrity.

## First 15 Minutes

1. Acknowledge incident in team channel and assign Incident Commander.
2. Capture current timestamp and affected endpoints/workflows.
3. Check API health endpoints:
   - `GET /api/v1/health/live`
   - `GET /api/v1/health/ready`
4. Check latest deployment and CI status for main branch.
5. Validate auth behavior with a login smoke call.
6. Decide severity level and communicate initial status.

## Triage Checklist

1. Runtime and startup guardrails:
   - Verify required production env vars are set (`SECRET_KEY`, `ADMIN_PASSWORD`, `CORS_ALLOW_ORIGINS`).
2. Auth and rate-limiting:
   - Check for abnormal login 429/401 spikes.
3. Data outputs:
   - Validate existence and freshness of scored outputs under `outputs/`.
4. Adapter mode:
   - Confirm `OUTPUT_STORE_ADAPTER` currently in use (`csv` or `db`).
5. Logs and traceability:
   - Correlate failing requests using `X-Request-ID`.

## Containment Actions

- If latest deploy is suspected, rollback to previous stable commit.
- If adapter migration is suspected, switch to `OUTPUT_STORE_ADAPTER=csv` and restart service.
- If bad outputs are suspected, rerun pipeline from a verified input snapshot.
- If auth abuse is suspected, tighten login rate limits temporarily.
- If async jobs are failing, inspect dead-letter jobs and requeue after fix using `POST /api/v1/jobs/{job_id}/requeue`.
- If an async job was submitted in error and still queued, cancel it via `POST /api/v1/jobs/{job_id}/cancel`.
- If queue growth is impacting storage or triage clarity, purge old terminal jobs via `POST /api/v1/jobs/cleanup?older_than_seconds=86400`.
- If worker interruption left jobs stuck in `running`, recover them via `POST /api/v1/jobs/recover-stale?stale_after_seconds=300`.
- Use `GET /api/v1/jobs?status=queued&limit=50` to inspect queue health and choose next recovery action.
- Use `GET /api/v1/jobs/stats` to quickly assess backlog size and concentration of `dead_letter` failures.
- Async submit endpoints deduplicate active jobs by default; use `?force=true` only when you intentionally need parallel reruns.
- During deploy/restart, worker shutdown is graceful; verify queue resumes by checking `GET /api/v1/jobs/stats` after service is healthy.
- If async submit returns HTTP 429, inspect queue depth and reduce submission rate or raise `JOB_MAX_QUEUED_JOBS` with controlled rollback plan.
- Use `POST /api/v1/jobs/pause` before maintenance actions and `POST /api/v1/jobs/resume` after verification to control background execution safely.
- Use `POST /api/v1/jobs/resume?require_drained=true` when you want resume to fail fast unless the queue is fully drained.
- While paused, async submit endpoints are expected to return HTTP `423 Locked`; resume processing before re-triggering jobs.
- To quickly drain unsafe backlog, use `POST /api/v1/jobs/cancel-queued` (optionally `?job_type=...`) before controlled recovery.
- Use `GET /api/v1/jobs/drain-status` to confirm paused mode has no running work before resume or deployment cutover.
- Use `POST /api/v1/jobs/drain-wait?timeout_seconds=30` to block briefly for drain completion and receive explicit timeout status.

## Recovery Verification

1. Run smoke checks:
   - Health/live and health/ready endpoints return success.
   - Login succeeds for admin test account.
   - Protected endpoint returns expected response.
2. Confirm CI checks are green on recovery commit:
   - pytest
   - ruff
   - mypy
3. Confirm business KPIs and output artifacts are restored.

## Communication Template

- Incident: [short title]
- Severity: [SEV-1/2/3]
- Start Time: [UTC]
- Impact: [users/workflows affected]
- Current Status: [triage/contained/recovering/resolved]
- Next Update ETA: [time]

## Post-Incident Review (Within 48h)

1. Root cause summary.
2. What detection worked/failed.
3. Corrective actions with owners and dates.
4. Runbook updates from lessons learned.
