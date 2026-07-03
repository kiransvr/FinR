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
