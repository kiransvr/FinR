# FinG Sprint 3 Backlog (Planning Only)

## 1. Sprint Status

- Status: Planning in progress
- Delivery mode: Planning-only (no development execution)
- Constraint: No budget or approval for development at this time
- Planned start: To be confirmed after budget and approval sign-off

## 2. Sprint Goal

Prepare implementation-ready Sprint 3 scope for loan onboarding and borrower-loan linkage, without starting code changes.

## 3. Scope Guardrails

- No code implementation, refactoring, or schema changes.
- No feature merge requests for Sprint 3 stories.
- Allowed activities: requirement refinement, API and UX design, dependency mapping, test planning, and estimation.
- Release impact: none until approval is granted.

## 4. Candidate Story Backlog (Draft, Not Approved for Dev)

| Priority | Story ID | Epic | Story | Points | Owner | Dependency | Status |
|---|---|---|---|---:|---|---|---|
| P1 | S3-01 | EPIC-02 | Loan domain model and persistence design | 8 | Backend Lead | S2 complete | Draft |
| P1 | S3-02 | EPIC-02 | Loan API contracts (create/view/search) design | 8 | Backend Engineer | S3-01 | Draft |
| P1 | S3-03 | EPIC-02 | Loan status and outstanding calculation rules | 5 | Backend Engineer | S3-01 | Draft |
| P2 | S3-04 | EPIC-02 | Web loan summary and detail UX design | 8 | Frontend Engineer | S3-02 | Draft |
| P2 | S3-05 | EPIC-02 | Mobile loan placeholder flow design | 5 | Mobile Engineer | S3-02 | Draft |
| P2 | S3-06 | EPIC-02 | Loan API contract and integration test plan | 5 | QA Engineer | S3-02, S3-04 | Draft |
| P3 | S3-07 | EPIC-02 | Sprint 3 observability and audit design | 3 | Backend Engineer | S3-02 | Draft |
| P3 | S3-08 | EPIC-02 | Sprint 3 security controls and checklist design | 3 | DevSecOps/Backend Lead | S3-02 | Draft |

Draft total: 45 points

## 5. Planning Deliverables

- Finalized acceptance criteria for S3-01 to S3-08.
- Updated API contract drafts for loan endpoints and error behavior.
- UX wireframes or flows for web and mobile loan screens.
- Dependency and risk log with mitigation owners.
- Sprint 3 test strategy (unit, contract, integration, security).
- Budget and approval decision record.

## 6. Entry Criteria to Start Development

Sprint 3 development can start only when all are true:
- Budget is approved.
- Product owner and engineering manager approval is recorded.
- Sprint 3 backlog is re-estimated and committed.
- Required environments and staffing are confirmed.

## 7. Ceremony Focus (Planning-Only Mode)

- Backlog refinement: tighten scope and remove ambiguity.
- Architecture/API review: finalize loan module boundaries.
- Estimation workshop: adjust points with current team capacity.
- Go/No-Go checkpoint: explicit sign-off to move from planning to execution.
