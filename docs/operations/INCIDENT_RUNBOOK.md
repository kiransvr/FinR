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
- For larger recovery windows, use `POST /api/v1/jobs/requeue-dead-letter?job_type=<type>&limit=100` to requeue dead-letter jobs in controlled batches.
- Use `dry_run=true` first to preview eligible dead-letter jobs before performing bulk requeue.
- If an async job was submitted in error and still queued, cancel it via `POST /api/v1/jobs/{job_id}/cancel`.
- If queue growth is impacting storage or triage clarity, purge old terminal jobs via `POST /api/v1/jobs/cleanup?older_than_seconds=86400`.
- If worker interruption left jobs stuck in `running`, recover them via `POST /api/v1/jobs/recover-stale?stale_after_seconds=300`.
- Use `GET /api/v1/jobs?status=queued&limit=50` to inspect queue health and choose next recovery action.
- Use `GET /api/v1/jobs/stats` to quickly assess backlog size and concentration of `dead_letter` failures.
- Use `GET /api/v1/jobs/stats-by-type` to identify which job types are driving queue pressure before requeue/cancel actions.
- Use `GET /api/v1/jobs/worker-status` to confirm the background worker is alive and whether paused workloads are fully drained.
- If worker liveness is false, run `POST /api/v1/jobs/restart-worker` and re-check `worker-status` before retrying queued operations.
- Prefer `POST /api/v1/jobs/ensure-worker-alive` for non-disruptive recovery when worker is down but you do not want a forced restart.
- Use `GET /api/v1/jobs/queue-age?threshold_seconds=300` to detect starvation risk from aged queued jobs.
- Use `GET /api/v1/jobs/queued-oldest?limit=20` to target the oldest queued work for cancel/requeue decisions.
- Use `GET /api/v1/jobs/dead-letter-rate?window_seconds=3600&threshold_per_minute=1` to monitor failure acceleration and trigger rapid rollback/escalation.
- Use `GET /api/v1/jobs/dead-letter-top-types?limit=10` to prioritize remediation on the highest-failing job types first.
- Use `GET /api/v1/jobs/dead-letter-errors?limit=10` to quickly identify dominant failure causes before requeue/retry actions.
- Use `GET /api/v1/jobs/dead-letter-recent?limit=20` to inspect freshest failure details and verify whether mitigations are taking effect.
- Use `GET /api/v1/jobs/dead-letter-trend?window_seconds=3600` to confirm whether dead-letter volume is trending up, down, or flat.
- Use `GET /api/v1/jobs/alerts` for a single severity snapshot combining worker liveness, queue-age breach, and dead-letter-rate breach.
- Use `GET /api/v1/jobs/alerts/signals` to inspect each worker/queue/dead-letter signal with explicit status and signal-level details.
- Use `GET /api/v1/jobs/alerts/failing-signals` to fetch only breached signals with recommended actions for faster triage.
- Use `GET /api/v1/jobs/alerts/recommendations` to retrieve immediate action guidance mapped to current alert signals.
- Use `GET /api/v1/jobs/alerts/health` in deployment/maintenance gates to enforce pass-fail criteria from current alert severity.
- Use `GET /api/v1/jobs/alerts/gate` for automation-friendly pass/fail with reasons; set `fail_on_warning=true` for stricter release gating.
- Use `GET /api/v1/jobs/alerts/gate/check` when your pipeline needs HTTP-native gating (`200` pass, `503` fail).
- Use `GET /api/v1/jobs/alerts/gate/matrix` to compare relaxed and strict gate policy outcomes before changing release thresholds.
- Use `GET /api/v1/jobs/alerts/gate/advice` to retrieve the recommended policy mode (`strict`, `relaxed`, or `block`) for current conditions.
- Use `GET /api/v1/jobs/alerts/gate/advice/check` for HTTP-native enforcement of policy advice (`200` allowed, `503` blocked).
- Use `GET /api/v1/jobs/alerts/gate/evaluate?mode=strict|relaxed|advice` when automation needs one endpoint for explicit mode evaluation.
- Use `GET /api/v1/jobs/alerts/gate/evaluate/check?mode=strict|relaxed|advice` when automation needs HTTP pass/fail for a selected evaluation mode.
- Use `GET /api/v1/jobs/alerts/gate/profile?profile=prod|staging|dev` to apply environment presets consistently across release pipelines.
- Use `GET /api/v1/jobs/alerts/gate/profile/check?profile=prod|staging|dev` when profile-based policy needs HTTP-native pass/fail gating.
- Use `GET /api/v1/jobs/alerts/gate/profile/matrix` to compare all environment profiles side-by-side before promoting releases.
- Use `GET /api/v1/jobs/alerts/gate/profile/matrix/check` for HTTP-native enforcement of the profile matrix recommendation.
- Use `GET /api/v1/jobs/alerts/gate/profile/rollout` to translate matrix output into an actionable release decision for operators.
- Use `GET /api/v1/jobs/alerts/gate/profile/rollout/check` when CI/CD should enforce rollout recommendation with HTTP status (`200` allow, `503` block).
- Use `GET /api/v1/jobs/alerts/gate/profile/rollout/plan` to inspect promotion path and per-stage eligibility before release.
- Use `GET /api/v1/jobs/alerts/gate/profile/rollout/plan/check` for HTTP-native pass/fail enforcement of rollout plan decisions.
- Use `GET /api/v1/jobs/alerts/gate/profile/rollout/summary` when release dashboards need a compact readiness verdict and stage counts.
- Use `GET /api/v1/jobs/alerts/gate/profile/rollout/summary/check` for HTTP-native enforcement of summary readiness in CI/CD.
- Async submit endpoints deduplicate active jobs by default; use `?force=true` only when you intentionally need parallel reruns.
- During deploy/restart, worker shutdown is graceful; verify queue resumes by checking `GET /api/v1/jobs/stats` after service is healthy.
- If async submit returns HTTP 429, inspect queue depth and reduce submission rate or raise `JOB_MAX_QUEUED_JOBS` with controlled rollback plan.
- Use `POST /api/v1/jobs/pause` before maintenance actions and `POST /api/v1/jobs/resume` after verification to control background execution safely.
- Use `POST /api/v1/jobs/resume?require_drained=true` when you want resume to fail fast unless the queue is fully drained.
- Use `POST /api/v1/jobs/resume-safe?timeout_seconds=30` for a one-call guarded resume that waits for drain and only resumes on success.
- While paused, async submit endpoints are expected to return HTTP `423 Locked`; resume processing before re-triggering jobs.
- To quickly drain unsafe backlog, use `POST /api/v1/jobs/cancel-queued` (optionally `?job_type=...`) before controlled recovery.
- For safer progressive drain, use `POST /api/v1/jobs/cancel-queued?limit=100` (optionally with `job_type`) and repeat in batches.
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
