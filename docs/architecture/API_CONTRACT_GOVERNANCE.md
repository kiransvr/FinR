# API Contract Governance

## Objective

Define and enforce stable API contracts so clients can integrate safely across releases.

## Versioning Standard

- Public API endpoints must be exposed under a major-version prefix: `/api/v1/...`.
- The FastAPI OpenAPI `info.version` must follow semantic versioning: `MAJOR.MINOR.PATCH`.
- Breaking API changes require a new major path version (for example, `/api/v2`).

## Backward-Compatible Change Rules

Allowed without major version bump:

- Adding new optional request fields.
- Adding new response fields that do not remove or rename existing fields.
- Adding new endpoints.

Not allowed without major version bump:

- Removing or renaming endpoints.
- Removing or renaming existing response fields.
- Changing required request fields incompatibly.

## Deprecation Policy

When an operation is deprecated:

- Mark operation as deprecated in OpenAPI (`deprecated: true`).
- Include `x-sunset-date` in `YYYY-MM-DD` format in the operation metadata.
- Keep endpoint available until sunset date and major-version cutover.

## CI Enforcement

Contract governance tests must pass in CI:

- API paths are versioned under `/api/v1`.
- OpenAPI semantic version format is valid.
- Deprecated operations include a valid sunset date extension.

## Release Practice

- Any API contract change must include test updates.
- Breaking changes must include migration notes and major-version rollout plan.
