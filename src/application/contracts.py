from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthStatus:
    status: str
    model_loaded: bool
    pipeline_outputs_available: bool


@dataclass(frozen=True)
class RecordPage:
    total: int
    records: list[dict]


@dataclass(frozen=True)
class FeedbackSubmission:
    AsOfDate: str
    OfficerId: str
    AccountId: str
    VisitStatus: str
    Outcome: str
    PromiseStatus: str
    PromiseToPayDate: str
    PromisedAmount: float
    ClientHardshipFlag: str
    DisputeFlag: str
    SupervisorEscalation: str
    NextAction: str
    FieldNotes: str


@dataclass(frozen=True)
class FeedbackSubmitResult:
    feedback_total: int
    record: dict


@dataclass(frozen=True)
class PlanRefreshResult:
    visit_plan_rows: int
    officer_kpi_rows: int
    feedback_rows: int


@dataclass(frozen=True)
class PipelineRunResult:
    scored_accounts: int
    top_risky_accounts: int
    visit_plan_rows: int
    officer_kpi_rows: int
