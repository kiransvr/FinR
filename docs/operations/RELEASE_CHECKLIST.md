# Release Checklist

## Pre-Release

1. Code and Branch State
- [ ] Branch is up to date with `main`.
- [ ] No uncommitted local changes.

2. Quality Gates (Must Pass)
- [ ] `pytest -q`
- [ ] `ruff check .`
- [ ] `mypy src`
- [ ] GitHub Actions `Python CI` workflow is green on target commit.

3. Configuration Readiness
- [ ] Production env vars validated (`APP_ENV`, `SECRET_KEY`, `ADMIN_PASSWORD`, `CORS_ALLOW_ORIGINS`).
- [ ] `OUTPUT_STORE_ADAPTER` confirmed (`csv` or `db`).
- [ ] Login rate limit settings reviewed for release traffic.

4. Data and Output Readiness
- [ ] Input data source for pipeline release run is validated.
- [ ] Expected output files generated and sanity-checked.

5. Deployment Strategy Readiness
- [ ] Blue/green target slot identified (`api-blue` or `api-green`).
- [ ] Candidate slot passes `/api/v1/health/live` and `/api/v1/health/ready`.
- [ ] Candidate slot passes smoke checks before traffic cutover.

## Release Execution

1. Tag and deploy approved commit.
2. Monitor startup logs for guardrail validation.
3. Run post-deploy smoke checks:
- [ ] `GET /api/v1/health/live`
- [ ] `GET /api/v1/health/ready`
- [ ] auth login and one protected endpoint call

## Post-Release Verification

- [ ] Error rate and latency are within expected range.
- [ ] No abnormal 401/403/429 spikes.
- [ ] Request IDs appear in logs for sampled requests.
- [ ] `/api/v1/metrics` reflects expected traffic and error profile.

## Rollback Criteria

- [ ] Health readiness fails for more than 5 minutes.
- [ ] Critical endpoint error rate exceeds threshold.
- [ ] Scoring outputs are missing or invalid.

## Sign-off

- Engineering Owner: __________________
- Date/Time (UTC): __________________
- Release Commit: __________________
