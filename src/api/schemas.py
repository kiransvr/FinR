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


class JobStatsCounts(BaseModel):
    queued: int
    running: int
    succeeded: int
    dead_letter: int
    canceled: int
    total: int


class JobStatsOldest(BaseModel):
    queued: str | None = None
    running: str | None = None
    dead_letter: str | None = None


class JobStatsResponse(BaseModel):
    status: str
    paused: bool
    counts: JobStatsCounts
    oldest: JobStatsOldest


class JobTypeStatsRecord(BaseModel):
    job_type: str
    queued: int
    running: int
    dead_letter: int
    total: int


class JobTypeStatsResponse(BaseModel):
    status: str
    records: list[JobTypeStatsRecord]


class JobWorkerStatusResponse(BaseModel):
    status: str
    worker_alive: bool
    paused: bool
    running: int
    queued: int
    drained: bool


class JobWorkerRestartResponse(BaseModel):
    status: str
    restarted: bool
    worker_alive: bool
    paused: bool
    running: int
    queued: int
    drained: bool


class JobWorkerEnsureResponse(BaseModel):
    status: str
    started: bool
    worker_alive: bool
    paused: bool
    running: int
    queued: int
    drained: bool


class JobQueueAgeResponse(BaseModel):
    status: str
    queued: int
    oldest_queued_at: str | None = None
    oldest_queued_age_seconds: float | None = None
    threshold_seconds: float
    breached: bool


class JobDeadLetterRateResponse(BaseModel):
    status: str
    window_seconds: float
    threshold_per_minute: float
    recent_dead_letter: int
    total_dead_letter: int
    rate_per_minute: float
    breached: bool


class JobAlertsSnapshotResponse(BaseModel):
    status: str
    severity: str
    breached: bool
    worker_alive: bool
    paused: bool
    queued: int
    running: int
    queue_age_breached: bool
    dead_letter_rate_breached: bool
    oldest_queued_age_seconds: float | None = None
    dead_letter_rate_per_minute: float


class JobAlertsRecommendationsResponse(BaseModel):
    status: str
    severity: str
    recommendations: list[str]


class JobAlertsHealthResponse(BaseModel):
    status: str
    severity: str
    healthy: bool
    fail_on_warning: bool


class JobAlertSignalRecord(BaseModel):
    name: str
    status: str
    breached: bool
    details: dict


class JobAlertsSignalsResponse(BaseModel):
    status: str
    severity: str
    breached: bool
    signals: list[JobAlertSignalRecord]


class JobFailingAlertSignalRecord(BaseModel):
    name: str
    status: str
    breached: bool
    details: dict
    recommendation: str


class JobAlertsFailingSignalsResponse(BaseModel):
    status: str
    severity: str
    breached: bool
    total_signals: int
    failing_count: int
    signals: list[JobFailingAlertSignalRecord]


class JobAlertsGateResponse(BaseModel):
    status: str
    severity: str
    breached: bool
    fail_on_warning: bool
    pass_gate: bool
    failing_count: int
    reasons: list[str]


class JobAlertsGateModeResult(BaseModel):
    fail_on_warning: bool
    pass_gate: bool
    failing_count: int
    reasons: list[str]
    recommended_status_code: int


class JobAlertsGateMatrixResponse(BaseModel):
    status: str
    severity: str
    breached: bool
    relaxed: JobAlertsGateModeResult
    strict: JobAlertsGateModeResult


class JobAlertsGateAdviceResponse(BaseModel):
    status: str
    severity: str
    breached: bool
    strict_pass: bool
    relaxed_pass: bool
    recommended_mode: str
    deployment_allowed: bool
    recommended_status_code: int
    reasons: list[str]


class JobAlertsGateEvaluateResponse(BaseModel):
    status: str
    severity: str
    breached: bool
    mode: str
    pass_gate: bool
    deployment_allowed: bool
    recommended_status_code: int
    reasons: list[str]
    effective_fail_on_warning: bool | None = None
    recommended_mode: str


class JobAlertsGateProfileResponse(BaseModel):
    status: str
    profile: str
    profile_mode: str
    severity: str
    breached: bool
    mode: str
    pass_gate: bool
    deployment_allowed: bool
    recommended_status_code: int
    reasons: list[str]
    effective_fail_on_warning: bool | None = None
    recommended_mode: str


class JobAlertsGateProfileResult(BaseModel):
    profile: str
    profile_mode: str
    severity: str
    breached: bool
    mode: str
    pass_gate: bool
    deployment_allowed: bool
    recommended_status_code: int
    reasons: list[str]
    effective_fail_on_warning: bool | None = None
    recommended_mode: str


class JobAlertsGateProfileMatrixResponse(BaseModel):
    status: str
    severity: str
    breached: bool
    recommended_profile: str
    deployment_allowed: bool
    recommended_status_code: int
    profiles: dict[str, JobAlertsGateProfileResult]


class JobAlertsGateProfileRolloutResponse(BaseModel):
    status: str
    severity: str
    breached: bool
    recommended_profile: str
    next_profile: str | None = None
    recommended_action: str
    deployment_allowed: bool
    recommended_status_code: int
    reasons: list[str]
    profiles: dict[str, JobAlertsGateProfileResult]


class JobAlertsGateProfileRolloutStage(BaseModel):
    profile: str
    eligible: bool
    recommended_status_code: int
    reasons: list[str]


class JobAlertsGateProfileRolloutPlanResponse(BaseModel):
    status: str
    severity: str
    breached: bool
    recommended_profile: str
    next_profile: str | None = None
    recommended_action: str
    deployment_allowed: bool
    recommended_status_code: int
    reasons: list[str]
    promotion_path: list[str]
    blocking_profiles: list[str]
    stages: list[JobAlertsGateProfileRolloutStage]


class JobAlertsGateProfileRolloutSummaryResponse(BaseModel):
    status: str
    severity: str
    breached: bool
    recommended_profile: str
    recommended_action: str
    deployment_allowed: bool
    recommended_status_code: int
    release_readiness: str
    highest_eligible_profile: str | None = None
    eligible_stages: int
    blocked_stages: int
    total_stages: int
    blocking_profiles: list[str]
    reasons: list[str]
    suppression_active: bool
    suppress_warning_until: str | None = None
    suppression_reason: str | None = None
    suppressed: bool


class JobAlertsGateProfileRolloutPolicyResponse(BaseModel):
    status: str
    policy: str
    queue_age_threshold_seconds: float
    dead_letter_window_seconds: float
    dead_letter_threshold_per_minute: float
    severity: str
    breached: bool
    recommended_profile: str
    recommended_action: str
    deployment_allowed: bool
    recommended_status_code: int
    release_readiness: str
    highest_eligible_profile: str | None = None
    eligible_stages: int
    blocked_stages: int
    total_stages: int
    blocking_profiles: list[str]
    reasons: list[str]


class JobDeadLetterTopTypeRecord(BaseModel):
    job_type: str
    dead_letter: int


class JobDeadLetterTopTypesResponse(BaseModel):
    status: str
    records: list[JobDeadLetterTopTypeRecord]


class JobDeadLetterErrorRecord(BaseModel):
    error_message: str
    dead_letter: int


class JobDeadLetterErrorsResponse(BaseModel):
    status: str
    records: list[JobDeadLetterErrorRecord]


class JobDeadLetterTrendResponse(BaseModel):
    status: str
    window_seconds: float
    recent_count: int
    previous_count: int
    delta: int
    direction: str


class JobCleanupResponse(BaseModel):
    status: str
    message: str
    deleted_count: int


class JobActionCountResponse(BaseModel):
    status: str
    message: str
    affected_count: int


class JobDrainStatusResponse(BaseModel):
    status: str
    paused: bool
    running: int
    queued: int
    drained: bool


class JobDrainWaitResponse(BaseModel):
    status: str
    paused: bool
    running: int
    queued: int
    drained: bool
    timed_out: bool
    timeout_seconds: float


class JobSafeResumeResponse(BaseModel):
    status: str
    resumed: bool
    paused: bool
    running: int
    queued: int
    drained: bool
    timed_out: bool
    timeout_seconds: float
