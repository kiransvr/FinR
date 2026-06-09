# FinG Sprint Plan (Initial 8 Sprints)

## Planning Assumptions

- Team composition: 1 backend lead, 2 backend engineers, 1 frontend engineer, 1 mobile engineer, 1 QA engineer, 1 product owner.
- Sprint duration: 2 weeks.
- Capacity baseline: 40-50 story points per sprint (to be recalibrated after Sprint 1).

## Epic Map

- EPIC-01 Platform Foundation
- EPIC-02 Borrower and Loan Core
- EPIC-03 Demand and Collections
- EPIC-04 Overdue and Recovery
- EPIC-05 Notifications and Dashboards
- EPIC-06 Reporting and Import/Cleansing
- EPIC-07 Hardening and Release

## Sprint Breakdown

### Sprint 1
Goals:
- Project foundations and engineering standards.

Planned outcomes:
- Backend layered structure finalized.
- DB migration pipeline and local compose finalized.
- API error model, validation baseline, health endpoints.
- Frontend/mobile app shells with auth placeholders.

### Sprint 2
Goals:
- Borrower module complete for CRUD and search.

Planned outcomes:
- Borrower APIs + DB schema extensions.
- Basic borrower list/detail screens (web/mobile).
- Unit tests and contract tests for borrower APIs.

### Sprint 3
Goals:
- Loan onboarding and linkage to borrower.

Current mode:
- Planning-only (no development execution) until budget and approval are granted.

Planned outcomes:
- Loan create/view APIs.
- Outstanding and status calculations.
- Loan summary UI components.

### Sprint 4
Goals:
- Demand generation and schedule workflows.

Planned outcomes:
- Demand generation service and API.
- Schedule recomputation and idempotency controls.
- Demand views in supervisor dashboard.

### Sprint 5
Goals:
- Collections posting and receipt lifecycle.

Planned outcomes:
- Collection posting APIs and receipt references.
- Audit trails for financial transactions.
- Mobile collection capture flow (online-first).

### Sprint 6
Goals:
- Overdue and recovery operations.

Planned outcomes:
- DPD bucketing and recovery case tracking.
- Follow-up action workflows.
- Notification triggers for due/overdue events.

### Sprint 7
Goals:
- Reporting, import/cleansing, and UAT readiness.

Planned outcomes:
- CSV exports and report filters.
- Import pipeline with validation/error report.
- UAT environment and test pack execution.

### Sprint 8
Goals:
- Hardening and production readiness.

Planned outcomes:
- Performance and security remediation.
- Go-live checklist completion.
- Release and hypercare preparation.

## Sprint KPIs

- Commitment reliability (% committed vs delivered).
- Defect leakage to UAT/Prod.
- Cycle time and lead time.
- Escaped defect severity profile.
- Automation coverage trend.

## Detailed Sprint Backlogs

- Sprint 1 detailed backlog: docs/SPRINT-1-BACKLOG.md
- Sprint 2 detailed backlog: docs/SPRINT-2-BACKLOG.md
- Sprint 3 detailed backlog: docs/SPRINT-3-BACKLOG.md
