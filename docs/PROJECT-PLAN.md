# FinG Project Plan

## 1. Delivery Model

- Methodology: Agile Scrum
- Sprint length: 2 weeks
- Release cadence: every 2 sprints (monthly)
- Estimation: story points (Fibonacci)
- Work tracking: Epic -> Feature -> Story -> Task

## 2. Delivery Phases

### Phase 0: Inception and Planning (Week 1-2)
- Finalize PRD and architecture baseline.
- Confirm module boundaries and ownership.
- Define environments, branching strategy, and CI quality gates.

Exit criteria:
- Approved requirements baseline.
- Approved architecture and ADRs.
- Ready backlog for Sprint 1.

### Phase 1: Foundation Build (Sprint 1-2)
- Set up backend, frontend, mobile skeletons.
- Implement auth, base API conventions, error model.
- Set up PostgreSQL migrations and Redis baseline.

Exit criteria:
- End-to-end hello flow across tiers.
- CI pipeline with build/test/lint/security scan.

### Phase 2: Core Business Capabilities (Sprint 3-6)
- Borrower + Loan + Demand + Collections modules.
- Overdue and Recovery workflows.
- Notification engine and core dashboards.

Current constraint note:
- Sprint 3 is in planning-only mode until budget and development approval are granted.

Exit criteria:
- MVP feature set complete.
- UAT-ready build with test evidence.

### Phase 3: Stabilization and Go-Live (Sprint 7-8)
- Performance tuning, security hardening.
- Data migration dry-runs and production checklist.
- UAT sign-off and controlled production rollout.

Exit criteria:
- Go-live readiness checklist completed.
- Hypercare support model active.

## 3. Work Breakdown Structure (WBS)

- Track A: Platform and DevOps
- Track B: Core Backend Domain Services
- Track C: Web Application
- Track D: Mobile App
- Track E: Data Migration and Reporting
- Track F: QA, Security, and Compliance

## 4. Environments

- Local: developer environment with Docker services.
- Dev: shared integration environment.
- UAT: business validation environment.
- Prod: controlled release environment.

## 5. Governance

- Daily standup: 15 minutes.
- Sprint planning: 2 hours per sprint.
- Backlog refinement: 1 hour weekly.
- Sprint review: 1 hour.
- Sprint retrospective: 45 minutes.
- Architecture review board: bi-weekly.

## 6. Quality Gates

- PR requires code review approval.
- Unit and integration test pass required.
- No critical/high vulnerabilities before release branch.
- API contract backward compatibility checks enforced.
- Flyway migration review for all schema changes.
- Protected branch requires passing GitHub Actions checks defined in `.github/workflows/`.

## 7. Definition of Ready (DoR)

A story is ready when:
- Business value and acceptance criteria are clear.
- Dependencies are identified.
- UX/API mocks are attached (if applicable).
- Test approach is agreed.

## 8. Definition of Done (DoD)

A story is done when:
- Code merged with peer review.
- Automated tests added and passing.
- Documentation updated.
- Security and logging checks completed.
- Product owner accepts against criteria.
