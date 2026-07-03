"""
Pydantic schemas for the Loan Default Risk API.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenRevokeRequest(BaseModel):
    token: str


class AuthActionResponse(BaseModel):
    status: str
    message: str


# ── Health ────────────────────────────────────────────────────────────────────

class LivenessResponse(BaseModel):
    status: str

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    pipeline_outputs_available: bool


class ApiErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ApiErrorResponse(BaseModel):
    error: ApiErrorBody


# ── Outputs ───────────────────────────────────────────────────────────────────

class ScoredAccountsResponse(BaseModel):
    total: int
    records: list[dict]


class VisitPlanResponse(BaseModel):
    total: int
    records: list[dict]


class OfficerKPIResponse(BaseModel):
    total: int
    records: list[dict]


class FeedbackSubmissionRequest(BaseModel):
    AsOfDate: str
    OfficerId: str
    AccountId: str
    VisitStatus: str = "Completed"
    Outcome: str = "Contacted"
    PromiseStatus: str = "None"
    PromiseToPayDate: str = ""
    PromisedAmount: float = 0.0
    ClientHardshipFlag: str = "No"
    DisputeFlag: str = "No"
    SupervisorEscalation: str = "No"
    NextAction: str = "Follow-up Call"
    FieldNotes: str = ""


class FeedbackSubmissionResponse(BaseModel):
    status: str
    message: str
    feedback_total: int
    record: dict


class FeedbackListResponse(BaseModel):
    total: int
    records: list[dict]


class PlanRefreshResponse(BaseModel):
    status: str
    message: str
    visit_plan_rows: int
    officer_kpi_rows: int
    feedback_rows: int


# ── Pipeline ──────────────────────────────────────────────────────────────────

class PipelineRunResponse(BaseModel):
    status: str
    message: str
    scored_accounts: Optional[int] = None
    top_risky_accounts: Optional[int] = None
    visit_plan_rows: Optional[int] = None
    officer_kpi_rows: Optional[int] = None


class JobSubmitResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    created_at: str


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    created_at: str
    updated_at: str
    result: dict | None = None
    error: str | None = None


class JobListResponse(BaseModel):
    total: int
    records: list[JobStatusResponse]


class JobCleanupResponse(BaseModel):
    status: str
    message: str
    deleted_count: int
