# Sprint 1 Security Baseline

## Implemented Controls

- Dependency vulnerability scan in CI with fail threshold (CVSS >= 7.0).
- Branch protection policy and required status checks documented.
- Correlation ID propagation for request traceability.
- Default secrets handling via environment variables for DB credentials.

## API Security Headers Baseline

Backend sets these response headers for all API responses:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'`
- `X-XSS-Protection: 0`

## CORS Baseline

Current baseline allows local development origins and can be overridden by env var:

- Default allowed origins:
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`
- Override with `CORS_ALLOWED_ORIGINS` (comma-separated values).
- Allowed methods: `GET,POST,PUT,PATCH,DELETE,OPTIONS`
- Allowed headers: `Authorization,Content-Type,X-Correlation-Id`

## Secrets Policy

- No secrets in source control.
- Use env variables for local and CI credentials.
- Rotate any credential immediately if exposed.

## Next Hardening Items

- Add JWT/OAuth2 authentication (Sprint 2+).
- Add rate limiting and request throttling.
- Add centralized security event logging.

## Sprint 2 Borrower API Security Delta (S2-08)

Borrower-specific hardening applied:

- Input validation tightened for borrower payloads:
  - `fullName` must be between 2 and 150 characters on create and update.
  - `phoneNumber` must be 10 to 15 digits on create, update, and search filter.
  - `status` constrained to `ACTIVE|CLOSED|BLOCKED` on update.
- Search query guardrails:
  - `page` must be >= 0.
  - `size` must be between 1 and 100.
  - `fullName` search filter must be 2 to 150 characters when provided.
- Security headers and CORS baseline explicitly contract-tested on borrower routes.

Evidence checklist:

- Contract test reports include borrower security checks:
  - `BorrowerControllerErrorContractTest`
  - `ApiSecurityHeadersContractTest`
- Borrower route responses include baseline headers:
  - `X-Content-Type-Options`
  - `X-Frame-Options`
  - `Referrer-Policy`
  - `Content-Security-Policy`
  - `X-XSS-Protection`
- CORS preflight remains successful for configured local origins on `/api/v1/borrowers`.
