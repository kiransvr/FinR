# Loan Default Early Warning Project

This project helps MFIs and loan officers identify which currently regular (`STD`) loan accounts are most likely to become delinquent or default later, so they can act early and focus collections effort where it matters most.

## What this project does

- Cleans and validates your loan dataset.
- Engineers key risk features:
  - Arrear ratio
  - LTV ratio
  - Interest stress
  - Delinquency and installment risk scores
- Builds a rule-based risk score for immediate business use.
- Trains a Logistic Regression model if future labels are available (`FutureStatusCode`).
- Scores currently regular accounts and outputs top risk accounts.
- Generates daily officer visit plans for medium/high-risk accounts.
- Produces per-officer collection KPI summaries and coaching hints.
- Exports a field feedback template to capture next-day planning inputs.

## Why it is used

- To detect risky borrowers early, before the account becomes harder to recover.
- To help loan officers prioritize the right cases instead of reviewing every account manually.
- To reduce collection cost and travel time by turning data into an action list.
- To support a more consistent, less reactive, and more auditable collections process.

## Expected input file

For development, use the included dummy input file:

- `data/raw/Loan Accounts-Dummy.csv`

Required columns:

- `CLStatusCode`
- `AgeDays`
- `DefaultedInst`
- `PrincipalOS`
- `PrincipalArrear`
- `InterestArrear`
- `TotalAccruedInt`
- `SecurityValue`
- `Sector`

Optional but recommended:

- `RepaymentFrequency`
- `FutureStatusCode` (needed for supervised ML training)
- `TotalInstallments`
- `Branch`

Runtime entry points:

- `python run_pipeline.py` to generate processed data, scores, and operational outputs
- `python run_api.py` to serve the FastAPI API
- `streamlit run app.py` to open the dashboard

Container entry points:

- `docker build -t loan-default-risk:local .`
- `docker run --rm -p 8001:8001 --env APP_ENV=production --env SECRET_KEY=<secret> --env ADMIN_PASSWORD=<password> loan-default-risk:local`
- `docker compose -f docker-compose.release.yml up -d api-blue --build`

Background job endpoints (admin):

- `POST /api/v1/jobs/pipeline/run` to execute full pipeline asynchronously
- `POST /api/v1/jobs/feedback/refresh-plan` to refresh visit plan asynchronously
- `GET /api/v1/jobs/{job_id}` to check job status and result (`queued`, `running`, `succeeded`, `dead_letter`)
- `POST /api/v1/jobs/{job_id}/requeue` (admin) to requeue dead-letter jobs
- `POST /api/v1/jobs/requeue-dead-letter` (admin) to requeue dead-letter jobs in bulk (`?job_type=...&limit=100&dry_run=true` optional)
- `POST /api/v1/jobs/{job_id}/cancel` (admin) to cancel queued jobs
- `POST /api/v1/jobs/cleanup?older_than_seconds=86400` (admin) to purge terminal jobs from durable queue
- `POST /api/v1/jobs/recover-stale?stale_after_seconds=300` (admin) to recover stale `running` jobs
- `GET /api/v1/jobs?status=queued&limit=50` (admin) to list recent jobs for triage
- `GET /api/v1/jobs/stats` (admin) to inspect queue backlog and status distribution
- `GET /api/v1/jobs/stats-by-type` (admin) to inspect backlog concentration by job type
- `GET /api/v1/jobs/worker-status` (admin) to verify worker liveness and current drain state
- `POST /api/v1/jobs/restart-worker` (admin) to restart the queue worker and return updated worker status
- `POST /api/v1/jobs/ensure-worker-alive` (admin) to start worker only if it is down and return current worker status
- `GET /api/v1/jobs/queue-age` (admin) to detect oldest queued job age breaches against an operational threshold
- `GET /api/v1/jobs/queued-oldest` (admin) to list oldest queued jobs for targeted triage
- `GET /api/v1/jobs/dead-letter-rate` (admin) to detect dead-letter growth rate breaches within an observation window
- `GET /api/v1/jobs/dead-letter-top-types` (admin) to identify job types producing most dead-letter failures
- `GET /api/v1/jobs/dead-letter-errors` (admin) to identify the most frequent dead-letter error reasons
- `GET /api/v1/jobs/dead-letter-recent` (admin) to inspect the latest dead-letter incidents and error details
- `GET /api/v1/jobs/dead-letter-trend` (admin) to compare recent dead-letter volume against the previous window
- `GET /api/v1/jobs/alerts` (admin) to get consolidated queue/worker alert severity in a single response
- `GET /api/v1/jobs/alerts/signals` (admin) to inspect worker/queue/dead-letter signals with per-signal status and details
- `GET /api/v1/jobs/alerts/failing-signals` (admin) to list only breached signals with recommendation text for rapid incident response
- `GET /api/v1/jobs/alerts/recommendations` (admin) to get action-oriented operational guidance from alert signals
- `GET /api/v1/jobs/alerts/health` (admin) to expose machine-friendly health (`ok/warning/critical`) for automation gates
- `GET /api/v1/jobs/alerts/gate` (admin) to return deployment gate pass/fail with explicit failure reasons (`?fail_on_warning=true` for strict mode)
- `GET /api/v1/jobs/alerts/gate/check` (admin) to return HTTP `200` on gate pass or `503` on gate fail for direct CI/CD enforcement
- `GET /api/v1/jobs/alerts/gate/matrix` (admin) to compare relaxed vs strict gate outcomes in one response for policy tuning
- `GET /api/v1/jobs/alerts/gate/advice` (admin) to get a recommended gate policy (`strict`, `relaxed`, or `block`) from current alert signals
- `GET /api/v1/jobs/alerts/gate/advice/check` (admin) to enforce policy advice via HTTP (`200` when deployment is allowed, `503` when blocked)
- `GET /api/v1/jobs/alerts/gate/evaluate?mode=strict|relaxed|advice` (admin) to evaluate a specific gate mode from one unified endpoint
- `GET /api/v1/jobs/alerts/gate/evaluate/check?mode=strict|relaxed|advice` (admin) to enforce selected mode via HTTP (`200` pass, `503` fail)
- `GET /api/v1/jobs/alerts/gate/profile?profile=prod|staging|dev` (admin) to evaluate environment policy presets (`prod=strict`, `staging=advice`, `dev=relaxed`)
- `GET /api/v1/jobs/alerts/gate/profile/check?profile=prod|staging|dev` (admin) to enforce profile policy via HTTP (`200` pass, `503` fail)
- `POST /api/v1/jobs/pause` and `POST /api/v1/jobs/resume` (admin) to toggle maintenance mode for background processing
- `POST /api/v1/jobs/resume?require_drained=true` (admin) to enforce that paused workers are drained before resuming
- `POST /api/v1/jobs/resume-safe?timeout_seconds=30` (admin) to wait for drain and resume in one guarded operation
- `POST /api/v1/jobs/cancel-queued` (admin) to bulk-cancel queued jobs (`?job_type=...&limit=100` optional)
- `GET /api/v1/jobs/drain-status` (admin) to verify whether paused processing is fully drained
- `POST /api/v1/jobs/drain-wait?timeout_seconds=30` (admin) to wait for paused workers to drain with timeout feedback

Async submit deduplication:

- `POST /api/v1/jobs/pipeline/run` and `POST /api/v1/jobs/feedback/refresh-plan` reuse an existing active (`queued` or `running`) job of the same type by default.
- Add `?force=true` to enqueue a new job even when an active one exists.

Worker lifecycle reliability:

- Background job worker now starts on API startup and stops gracefully on API shutdown to avoid orphan processing threads during restart/deploy.
- While processing is paused (`POST /api/v1/jobs/pause`), async submit endpoints return HTTP `423 Locked` until resumed.

Auth security endpoints:

- `POST /api/v1/auth/logout` revokes current bearer token
- `POST /api/v1/auth/revoke` (admin) revokes a provided bearer token

Observability endpoint (admin):

- `GET /api/v1/metrics` returns Prometheus-compatible API metrics text

In the dashboard, use the sidebar upload control to replace the active input file and run the pipeline from the UI.

## Security configuration

The API supports environment-driven security settings:

- `SECRET_KEY`: JWT signing key. Required for production (`APP_ENV=production`).
- `AUTH_KEY_VERSION`: token key version marker (default `v1`). Increment to invalidate prior token generations.
- `APP_ENV`: `development` (default) or `production`.
- `CORS_ALLOW_ORIGINS`: comma-separated trusted origins (default: `http://localhost:3000,http://localhost:8501`).
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`: admin credentials for demo auth.
- `ENABLE_DEMO_OFFICER_USER`: set to `false` to disable the seeded officer user.
- `OFFICER_USERNAME`, `OFFICER_PASSWORD`: optional demo officer credentials.
- `OUTPUT_STORE_ADAPTER`: output store adapter selector (`csv` default, `db` for SQL-backed mode; `db_stub` kept as compatibility alias).
- `DB_OUTPUT_DATABASE_URL`: optional SQLAlchemy DB URL for output persistence. Defaults to local SQLite at `outputs/output_store.db`.
- `JOB_QUEUE_DB_PATH`: optional durable job queue SQLite path. Defaults to `outputs/job_queue.db`.
- `JOB_MAX_ATTEMPTS`: max retry attempts per background job before dead-letter (default `3`).
- `JOB_RETRY_BACKOFF_SECONDS`: linear retry backoff base seconds (default `0.2`).
- `JOB_TIMEOUT_SECONDS`: per-job execution timeout before retry/dead-letter handling (default `60`).
- `JOB_RUNNING_STALE_SECONDS`: threshold for auto-recovering stale `running` jobs in worker loop (default `300`).
- `JOB_MAX_QUEUED_JOBS`: queue backpressure limit for `queued` jobs; async submit returns HTTP 429 when exceeded (default `500`).

Operational docs:

- `docs/operations/SECURITY_CONFIGURATION_CHECKLIST.md`
- `docs/operations/INCIDENT_RUNBOOK.md`
- `docs/operations/RELEASE_CHECKLIST.md`
- `docs/operations/DEPLOYMENT_STRATEGY.md`

API governance docs:

- `docs/architecture/API_CONTRACT_GOVERNANCE.md`

## Quick start

```powershell
cd loan-default-risk-project
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python run_pipeline.py
```

The pipeline will read the dummy CSV by default. Replace it later with your real branch or MFI data when you are ready.

## Outputs

- `data/processed/loan_accounts_processed.csv`
- `outputs/scored_accounts.csv`
- `outputs/top_risky_accounts.csv`
- `outputs/model_metrics.json` (only if `FutureStatusCode` exists)
- `models/default_risk_model.joblib` (only if `FutureStatusCode` exists)
- `outputs/daily_visit_plan.csv`
- `outputs/officer_kpis.csv`
- `outputs/field_feedback_template.csv`

## Risk logic used

Rule score:

- DelinquencyScore * 30
- InstallmentRisk * 25
- LTVRatio > 0.8 -> +20 else +10
- ArrearRatio > 0.3 -> +25 else +10

Rule categories:

- High Risk: score >= 70
- Medium Risk: score >= 40 and < 70
- Low Risk: score < 40

## Notes

- If `FutureStatusCode` is not present, the pipeline still works in rule-based mode.
- To get model-based default probability, include `FutureStatusCode` in historical data.
