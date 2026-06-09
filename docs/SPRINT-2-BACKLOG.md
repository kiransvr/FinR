# FinG Sprint 2 Backlog (Execution Ready)

## Sprint Status

- Status: Closed
- Closure date: 2026-06-09
- Closure note: Core Sprint 2 scope (S2-01 to S2-08) is complete and accepted.

## 1. Sprint Goal

Deliver end-to-end borrower management (create, update, view, search) across backend APIs, web UI, and mobile shell, with production-grade validation, test coverage, and release evidence.

## 2. Sprint Window

- Duration: 2 weeks
- Capacity target: 45 story points
- Scope policy: no mid-sprint scope addition without trade-off approval

## 3. Prioritized Story Backlog

| Priority | Story ID | Epic | Story | Points | Owner | Dependency |
|---|---|---|---|---:|---|---|
| P1 | S2-01 | EPIC-02 | Borrower domain and persistence expansion | 8 | Backend Lead | S1-01, S1-02 |
| P1 | S2-02 | EPIC-02 | Borrower API completion (create, update, get, search) | 8 | Backend Engineer | S2-01, S1-03 |
| P1 | S2-03 | EPIC-02 | Borrower search performance baseline | 5 | Backend Engineer | S2-01 |
| P1 | S2-04 | EPIC-02 | Web borrower screens (list, detail, create/edit) | 8 | Frontend Engineer | S2-02, S1-05 |
| P2 | S2-05 | EPIC-02 | Mobile borrower flow placeholder integration | 5 | Mobile Engineer | S2-02, S1-06 |
| P2 | S2-06 | EPIC-02 | API contract and integration test pack | 5 | QA Engineer | S2-02, S2-04 |
| P2 | S2-07 | EPIC-02 | Sprint 2 observability and audit enrichment | 3 | Backend Engineer | S2-02, S1-07 |
| P3 | S2-08 | EPIC-02 | Sprint 2 security hardening for borrower APIs | 3 | DevSecOps/Backend Lead | S2-02, S1-09 |

Planned total: 45 points

## 4. Detailed Stories

### S2-01 Borrower Domain and Persistence Expansion (8 SP)

Description:
Complete borrower domain model and persistence capabilities needed for full CRUD + search behavior.

Acceptance criteria:
- Borrower aggregate supports lifecycle status values: active, closed, blocked.
- Persistence model includes fields required by FR-001 and data dictionary.
- Repository supports lookup by borrower ID and query primitives for search.
- Flyway migration updates are versioned and backward-safe.

Tasks:
- Finalize borrower domain invariants and status transitions.
- Extend JPA entity and repository mapping.
- Add migration for new borrower attributes/indexes.
- Add unit tests for domain and repository adapter behavior.

Requirement mapping:
- Supports FR-001 and NFR-004.

### S2-02 Borrower API Completion (8 SP)

Description:
Expose complete borrower API surface for create, update, view, and search with stable contracts.

Acceptance criteria:
- `POST /api/v1/borrowers` creates borrower and returns unique ID.
- `PUT /api/v1/borrowers/{borrowerId}` updates mutable borrower fields.
- `GET /api/v1/borrowers/{borrowerId}` returns borrower detail.
- `GET /api/v1/borrowers` supports search by ID, phone, and name with pagination.
- Validation and error contract remain consistent with Sprint 1 standards.

Tasks:
- Implement missing controller endpoints and DTOs.
- Add application service methods and request validation.
- Standardize query parameters for search and paging.
- Add API examples to docs and response schema notes.

Requirement mapping:
- Supports FR-001 and NFR-004.

### S2-03 Borrower Search Performance Baseline (5 SP)

Description:
Meet initial performance target for borrower search and protect response times with index strategy.

Acceptance criteria:
- Search query plan uses supporting indexes for ID, phone, and name access paths.
- Baseline performance test demonstrates < 2 seconds for configured dataset profile.
- Paging defaults and upper bounds prevent unbounded scans.
- Performance assumptions and limits are documented.

Tasks:
- Add database indexes through Flyway.
- Add repository query strategy for indexed search.
- Add lightweight performance verification script/test.
- Document search constraints and expected scaling path.

Requirement mapping:
- Supports FR-001 acceptance criteria and NFR-002.

### S2-04 Web Borrower Screens (8 SP)

Description:
Deliver borrower list, detail, and create/edit flows in Next.js using the established app shell.

Acceptance criteria:
- Borrower list screen shows paginated search results.
- Borrower detail screen shows complete profile data and lifecycle status.
- Create/edit form validates required fields before submit.
- Web flow handles API validation and not-found errors using existing contract shape.
- Smoke and component tests cover critical borrower UI paths.

Tasks:
- Add borrower routes/pages and client state wiring.
- Implement reusable borrower form components.
- Integrate API client calls and error handling.
- Add UI tests for list/detail/form scenarios.

Requirement mapping:
- Supports FR-001 and NFR-004.

### S2-05 Mobile Borrower Flow Placeholder Integration (5 SP)

Description:
Extend mobile shell with borrower list/detail placeholders wired to borrower APIs.

Acceptance criteria:
- Mobile app includes borrower list and detail routes.
- API service abstraction supports borrower fetch and search calls.
- Placeholder create/edit action path is visible for future full mobile delivery.
- Widget/service tests cover route rendering and API service integration stubs.

Tasks:
- Add borrower feature folder structure in mobile module.
- Implement list/detail placeholder screens.
- Extend mobile API client and mapping models.
- Add tests for borrower routes and service behavior.

Requirement mapping:
- Supports FR-001 and FR-004 enablement.

### S2-06 API Contract and Integration Test Pack (5 SP)

Description:
Strengthen regression safety for borrower APIs with contract and integration verification.

Acceptance criteria:
- Contract tests validate success and error responses for all borrower endpoints.
- Integration tests cover create-update-get-search path against PostgreSQL.
- CI workflow executes borrower API test pack on pull requests.
- Test report artifacts are available for sprint review.

Tasks:
- Add API contract tests for CRUD and search scenarios.
- Add integration tests with local PostgreSQL profile.
- Update CI job matrix or stages for borrower pack.
- Document test evidence collection steps.

Requirement mapping:
- Supports FR-001 quality and NFR-006.

### S2-07 Sprint 2 Observability and Audit Enrichment (3 SP)

Description:
Improve borrower operation traceability with structured logs, correlation, and audit metadata.

Acceptance criteria:
- Borrower create/update/search logs include correlation ID and operation outcome.
- Audit fields (actor/time/source placeholder) are captured for borrower mutations.
- Actuator health/info remain available and metrics notes are updated.

Tasks:
- Add structured logging for borrower API operations.
- Add audit metadata handling in mutation pathways.
- Update observability notes in setup/ops docs.

Requirement mapping:
- Supports NFR-004, NFR-006, and NFR-001.

### S2-08 Sprint 2 Security Hardening for Borrower APIs (3 SP)

Description:
Apply borrower-specific security guardrails before expanding to loan module.

Acceptance criteria:
- Input validation covers all externally supplied borrower fields.
- CORS and security header baseline remains enforced for borrower routes.
- Security checklist is updated with borrower-specific checks and evidence.

Tasks:
- Review and tighten borrower DTO validations.
- Add/update security-focused tests for borrower endpoints.
- Extend security baseline notes with Sprint 2 deltas.

Requirement mapping:
- Supports NFR-003 and NFR-007.

## 5. Sprint Ceremonies and Control

- Sprint planning output: this backlog is frozen at planning close.
- Daily standup focus: blocker removal for P1 borrower delivery path.
- Mid-sprint review: confirm backend API completion by midpoint.
- End-sprint review: demo borrower CRUD + search across backend/web/mobile.

## 6. Definition of Done Applied to Sprint 2

A Sprint 2 story is accepted only when:
- Code is merged with peer review.
- Tests are added and passing in CI.
- Documentation is updated for changed behavior.
- Security and logging checks are satisfied.
- Product owner accepts based on listed criteria.

## 7. Stretch Candidates (Only if Capacity Remains)

- ST2-01 Publish OpenAPI v1 borrower contract.
- ST2-02 Add Testcontainers-backed borrower integration tests.
- ST2-03 Add borrower list export (CSV) for supervisor preview.

## 8. Deferred to Future Sprint

- ST2-01 Publish OpenAPI v1 borrower contract.
- ST2-02 Add Testcontainers-backed borrower integration tests.
- ST2-03 Add borrower list export (CSV) for supervisor preview.
- Deferred reason: Prioritized for later due to current budget/approval constraints on new development.
