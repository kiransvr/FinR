# Security Configuration Checklist

## Scope

Baseline controls required before deploying this service to shared or production environments.

## Secrets and Credentials

- [ ] `APP_ENV=production` in production.
- [ ] `SECRET_KEY` is set and not using default dev value.
- [ ] `ADMIN_PASSWORD` is set to a strong secret.
- [ ] Secrets are sourced from a secure store, not committed to repo.

## CORS and Network

- [ ] `CORS_ALLOW_ORIGINS` is explicitly set to trusted origins only.
- [ ] No wildcard origins in production.
- [ ] API ingress is limited by firewall/security group rules.

## Authentication and Access

- [ ] Demo officer user disabled in production if not required (`ENABLE_DEMO_OFFICER_USER=false`).
- [ ] Role checks enforced for admin-only endpoints.
- [ ] Login rate limits configured for environment capacity.
- [ ] `AUTH_KEY_VERSION` is set and rotated as part of key lifecycle policy.
- [ ] Token revocation flow is tested (`/api/v1/auth/logout`, `/api/v1/auth/revoke`).

## Data Protection

- [ ] Raw sensitive datasets are excluded from version control.
- [ ] Output artifacts reviewed for PII leakage risk.
- [ ] Backups and retention policy defined for production datastore.

## Build and Dependency Security

- [ ] CI pipeline runs tests (`pytest`), lint (`ruff`), and type checks (`mypy`).
- [ ] Dependency updates reviewed regularly.
- [ ] Release changes require code review approval.

## Observability and Auditability

- [ ] `X-Request-ID` propagation enabled and logged.
- [ ] Error responses use structured envelope for consistent monitoring.
- [ ] Incident runbook documented and accessible.

## Release Gate

- [ ] All items above checked before production release.
- [ ] Approval recorded by engineering owner.
