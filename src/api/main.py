"""
Loan Default Risk API — FastAPI application.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from typing import cast

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from src.application.access_policy import AuthorizationError, require_role
from src.application.contracts import FeedbackSubmission
from src.application.job_service import JobService
from src.application.job_service import QueueCapacityExceededError
from src.application.job_service import ProcessingPausedError
from src.application.risk_service import NotFoundError, RiskService
from src.api.auth import (
    TokenData,
    authenticate_user, create_access_token, get_current_user, get_bearer_token, revoke_access_token,
)
from src.api.guardrails import enforce_runtime_settings
from src.api.observability import install_observability_middleware
from src.api.observability import REQUEST_ID_HEADER, get_observability_store
from src.api.rate_limit import SlidingWindowRateLimiter
from src.api.schemas import (
    ApiErrorBody,
    ApiErrorResponse,
    HealthResponse,
    LivenessResponse,
    LoginRequest as SchemaLoginRequest,
    TokenResponse,
    TokenRevokeRequest,
    AuthActionResponse,
    ScoredAccountsResponse, VisitPlanResponse, OfficerKPIResponse,
    PipelineRunResponse,
    FeedbackSubmissionRequest,
    FeedbackSubmissionResponse,
    FeedbackListResponse,
    PlanRefreshResponse,
    JobSubmitResponse,
    JobStatusResponse,
    JobListResponse,
    JobStatsResponse,
    JobStatsCounts,
    JobStatsOldest,
    JobTypeStatsResponse,
    JobTypeStatsRecord,
    JobWorkerStatusResponse,
    JobWorkerRestartResponse,
    JobWorkerEnsureResponse,
    JobQueueAgeResponse,
    JobDeadLetterRateResponse,
    JobAlertsSnapshotResponse,
    JobAlertsRecommendationsResponse,
    JobAlertsHealthResponse,
    JobAlertsSignalsResponse,
    JobAlertSignalRecord,
    JobAlertsFailingSignalsResponse,
    JobFailingAlertSignalRecord,
    JobAlertsGateResponse,
    JobAlertsGateMatrixResponse,
    JobAlertsGateModeResult,
    JobAlertsGateAdviceResponse,
    JobAlertsGateEvaluateResponse,
    JobAlertsGateProfileResponse,
    JobAlertsGateProfileResult,
    JobAlertsGateProfileMatrixResponse,
    JobDeadLetterTopTypeRecord,
    JobDeadLetterTopTypesResponse,
    JobDeadLetterErrorRecord,
    JobDeadLetterErrorsResponse,
    JobDeadLetterTrendResponse,
    JobCleanupResponse,
    JobActionCountResponse,
    JobDrainStatusResponse,
    JobDrainWaitResponse,
    JobSafeResumeResponse,
)
from src.bootstrap.service_factory import build_risk_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
_risk_service = build_risk_service(BASE_DIR)
_job_service = JobService(
    db_path=Path(os.getenv("JOB_QUEUE_DB_PATH", (BASE_DIR / "outputs" / "job_queue.db").as_posix())),
    max_attempts=int(os.getenv("JOB_MAX_ATTEMPTS", "3")),
    retry_backoff_seconds=float(os.getenv("JOB_RETRY_BACKOFF_SECONDS", "0.2")),
    default_timeout_seconds=float(os.getenv("JOB_TIMEOUT_SECONDS", "60")),
    running_stale_seconds=float(os.getenv("JOB_RUNNING_STALE_SECONDS", "300")),
    max_queued_jobs=int(os.getenv("JOB_MAX_QUEUED_JOBS", "500")),
)
_job_service.register_handler("pipeline_run", lambda _: _risk_service.run_pipeline().__dict__)
_job_service.register_handler("refresh_plan", lambda _: _risk_service.refresh_plan_from_feedback().__dict__)
_login_rate_limiter = SlidingWindowRateLimiter(
    limit=int(os.getenv("LOGIN_RATE_LIMIT", "30")),
    window_seconds=int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "60")),
)


def get_risk_service() -> RiskService:
    return _risk_service


def get_job_service() -> JobService:
    return _job_service


def _raise_not_found(exc: NotFoundError) -> None:
    raise HTTPException(status_code=404, detail=str(exc))


def _get_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:8501")
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return origins or ["http://localhost:3000", "http://localhost:8501"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    enforce_runtime_settings()
    _job_service.start_worker()
    try:
        yield
    finally:
        _job_service.stop_worker()

app = FastAPI(
    title="Loan Default Risk",
    description="Collection operations, risk scoring, and visit planning for field officers.",
    version="1.0.0",
    lifespan=lifespan,
)

_cors_origins = _get_cors_origins()
_allow_credentials = "*" not in _cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_observability_middleware(app)


def _build_error_response(
    status_code: int,
    code: str,
    message: str,
    request: Request,
) -> JSONResponse:
    request_id = request.headers.get(REQUEST_ID_HEADER)
    payload = ApiErrorResponse(
        error=ApiErrorBody(code=code, message=message, request_id=request_id)
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    message = str(exc.detail) if exc.detail is not None else "Request failed"
    return _build_error_response(
        status_code=exc.status_code,
        code=f"HTTP_{exc.status_code}",
        message=message,
        request=request,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server error", exc_info=exc)
    return _build_error_response(
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message="Internal server error",
        request=request,
    )


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(body: SchemaLoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{body.username.lower()}"
    if not _login_rate_limiter.allow(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )

    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": user.username, "role": user.role})
    return TokenResponse(access_token=token)


@app.post("/api/v1/auth/logout", response_model=AuthActionResponse, tags=["Auth"])
def logout(
    _: TokenData = Depends(get_current_user),
    token: str = Depends(get_bearer_token),
):
    if not token or not revoke_access_token(token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token revocation failed")
    return AuthActionResponse(status="success", message="Token revoked successfully")


@app.post("/api/v1/auth/revoke", response_model=AuthActionResponse, tags=["Auth"])
def revoke_token(
    body: TokenRevokeRequest,
    current_user: TokenData = Depends(get_current_user),
):
    require_role(current_user.role, "admin")
    if not revoke_access_token(body.token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token revocation failed")
    return AuthActionResponse(status="success", message="Token revoked successfully")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/v1/health/live", response_model=LivenessResponse, tags=["Health"])
def live_health():
    return LivenessResponse(status="alive")


@app.get("/api/v1/health/ready", response_model=HealthResponse, tags=["Health"])
def ready_health(service: RiskService = Depends(get_risk_service)):
    health_status = service.get_health()
    return HealthResponse(
        status=health_status.status,
        model_loaded=health_status.model_loaded,
        pipeline_outputs_available=health_status.pipeline_outputs_available,
    )

@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
def health(service: RiskService = Depends(get_risk_service)):
    return ready_health(service)


@app.get("/api/v1/metrics", response_class=PlainTextResponse, tags=["Observability"])
def metrics(_: TokenData = Depends(get_current_user)):
    return PlainTextResponse(get_observability_store().render_prometheus())


# ── Outputs ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/scored-accounts", response_model=ScoredAccountsResponse, tags=["Outputs"])
def scored_accounts(
    limit: int = Query(default=200, ge=1, le=5000),
    _: TokenData = Depends(get_current_user),
    service: RiskService = Depends(get_risk_service),
):
    try:
        page = service.get_scored_accounts(limit)
        return ScoredAccountsResponse(total=page.total, records=page.records)
    except NotFoundError as exc:
        _raise_not_found(exc)


@app.get("/api/v1/top-risky", response_model=ScoredAccountsResponse, tags=["Outputs"])
def top_risky(
    limit: int = Query(default=100, ge=1, le=5000),
    _: TokenData = Depends(get_current_user),
    service: RiskService = Depends(get_risk_service),
):
    try:
        page = service.get_top_risky(limit)
        return ScoredAccountsResponse(total=page.total, records=page.records)
    except NotFoundError as exc:
        _raise_not_found(exc)


@app.get("/api/v1/visit-plan", response_model=VisitPlanResponse, tags=["Outputs"])
def visit_plan(
    _: TokenData = Depends(get_current_user),
    service: RiskService = Depends(get_risk_service),
):
    try:
        page = service.get_visit_plan()
        return VisitPlanResponse(total=page.total, records=page.records)
    except NotFoundError as exc:
        _raise_not_found(exc)


@app.get("/api/v1/officer-kpis", response_model=OfficerKPIResponse, tags=["Outputs"])
def officer_kpis(
    _: TokenData = Depends(get_current_user),
    service: RiskService = Depends(get_risk_service),
):
    try:
        page = service.get_officer_kpis()
        return OfficerKPIResponse(total=page.total, records=page.records)
    except NotFoundError as exc:
        _raise_not_found(exc)


@app.get("/api/v1/feedback", response_model=FeedbackListResponse, tags=["Feedback"])
def list_feedback(
    limit: int = Query(default=500, ge=1, le=5000),
    _: TokenData = Depends(get_current_user),
    service: RiskService = Depends(get_risk_service),
):
    page = service.list_feedback(limit)
    return FeedbackListResponse(total=page.total, records=page.records)


@app.post("/api/v1/feedback/submit", response_model=FeedbackSubmissionResponse, tags=["Feedback"])
def submit_feedback(
    body: FeedbackSubmissionRequest,
    current_user: TokenData = Depends(get_current_user),
    service: RiskService = Depends(get_risk_service),
):
    try:
        submission = FeedbackSubmission(**body.model_dump())
        result = service.submit_feedback(
            payload=submission,
            recorded_by=current_user.username,
        )
        return FeedbackSubmissionResponse(
            status="success",
            message="Feedback saved successfully.",
            feedback_total=result.feedback_total,
            record=result.record,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Feedback save failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/feedback/refresh-plan", response_model=PlanRefreshResponse, tags=["Feedback"])
def refresh_plan_from_feedback(
    current_user: TokenData = Depends(get_current_user),
    service: RiskService = Depends(get_risk_service),
):
    try:
        require_role(current_user.role, "admin")
        result = service.refresh_plan_from_feedback()
        return PlanRefreshResponse(
            status="success",
            message="Visit plan and officer KPIs refreshed from latest feedback.",
            visit_plan_rows=result.visit_plan_rows,
            officer_kpi_rows=result.officer_kpi_rows,
            feedback_rows=result.feedback_rows,
        )
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except NotFoundError as exc:
        _raise_not_found(exc)
    except Exception as exc:
        logger.exception("Plan refresh from feedback failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Pipeline trigger ──────────────────────────────────────────────────────────

@app.post("/api/v1/pipeline/run", response_model=PipelineRunResponse, tags=["Pipeline"])
def run_pipeline(
    current_user: TokenData = Depends(get_current_user),
    service: RiskService = Depends(get_risk_service),
):
    """Trigger the full pipeline (admin only). Retrains model and refreshes all outputs."""
    try:
        require_role(current_user.role, "admin")
        result = service.run_pipeline()
        return PipelineRunResponse(
            status="success",
            message="Pipeline completed successfully.",
            scored_accounts=result.scored_accounts,
            top_risky_accounts=result.top_risky_accounts,
            visit_plan_rows=result.visit_plan_rows,
            officer_kpi_rows=result.officer_kpi_rows,
        )
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        logger.exception("Pipeline run failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/jobs/pipeline/run", response_model=JobSubmitResponse, status_code=202, tags=["Jobs"])
def run_pipeline_async(
    force: bool = Query(default=False),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    try:
        if force:
            state = jobs.submit(job_type="pipeline_run", payload={})
        else:
            state, _ = jobs.submit_deduplicated(job_type="pipeline_run", payload={})
    except ProcessingPausedError as exc:
        raise HTTPException(status_code=423, detail=str(exc))
    except QueueCapacityExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    return JobSubmitResponse(
        job_id=state.job_id,
        job_type=state.job_type,
        status=state.status,
        created_at=state.created_at,
    )


@app.post(
    "/api/v1/jobs/feedback/refresh-plan",
    response_model=JobSubmitResponse,
    status_code=202,
    tags=["Jobs"],
)
def refresh_plan_async(
    force: bool = Query(default=False),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    try:
        if force:
            state = jobs.submit(job_type="refresh_plan", payload={})
        else:
            state, _ = jobs.submit_deduplicated(job_type="refresh_plan", payload={})
    except ProcessingPausedError as exc:
        raise HTTPException(status_code=423, detail=str(exc))
    except QueueCapacityExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    return JobSubmitResponse(
        job_id=state.job_id,
        job_type=state.job_type,
        status=state.status,
        created_at=state.created_at,
    )


@app.get("/api/v1/jobs", response_model=JobListResponse, tags=["Jobs"])
def list_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    states = jobs.list_jobs(status_filter=status_filter, limit=limit)
    records = [
        JobStatusResponse(
            job_id=state.job_id,
            job_type=state.job_type,
            status=state.status,
            created_at=state.created_at,
            updated_at=state.updated_at,
            result=state.result,
            error=state.error,
        )
        for state in states
    ]
    return JobListResponse(total=len(records), records=records)


@app.get("/api/v1/jobs/stats", response_model=JobStatsResponse, tags=["Jobs"])
def get_job_stats(
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    stats = jobs.get_job_stats()
    counts = cast(dict[str, int], stats["counts"])
    oldest = cast(dict[str, str | None], stats["oldest"])
    return JobStatsResponse(
        status="success",
        paused=bool(stats["paused"]),
        counts=JobStatsCounts(
            queued=int(counts["queued"]),
            running=int(counts["running"]),
            succeeded=int(counts["succeeded"]),
            dead_letter=int(counts["dead_letter"]),
            canceled=int(counts["canceled"]),
            total=int(counts["total"]),
        ),
        oldest=JobStatsOldest(
            queued=oldest["queued"],
            running=oldest["running"],
            dead_letter=oldest["dead_letter"],
        ),
    )


@app.get("/api/v1/jobs/stats-by-type", response_model=JobTypeStatsResponse, tags=["Jobs"])
def get_job_type_stats(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    rows = jobs.get_job_type_stats(limit=limit)
    records = [
        JobTypeStatsRecord(
            job_type=str(cast(dict[str, object], row)["job_type"]),
            queued=cast(int, cast(dict[str, object], row)["queued"]),
            running=cast(int, cast(dict[str, object], row)["running"]),
            dead_letter=cast(int, cast(dict[str, object], row)["dead_letter"]),
            total=cast(int, cast(dict[str, object], row)["total"]),
        )
        for row in rows
    ]
    return JobTypeStatsResponse(status="success", records=records)


@app.get("/api/v1/jobs/queue-age", response_model=JobQueueAgeResponse, tags=["Jobs"])
def get_job_queue_age(
    threshold_seconds: float = Query(default=300.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    age = cast(dict[str, object], jobs.get_queue_age_status(threshold_seconds=threshold_seconds))
    return JobQueueAgeResponse(
        status="success",
        queued=cast(int, age["queued"]),
        oldest_queued_at=cast(str | None, age["oldest_queued_at"]),
        oldest_queued_age_seconds=cast(float | None, age["oldest_queued_age_seconds"]),
        threshold_seconds=float(cast(float, age["threshold_seconds"])),
        breached=bool(age["breached"]),
    )


@app.get("/api/v1/jobs/queued-oldest", response_model=JobListResponse, tags=["Jobs"])
def list_oldest_queued_jobs(
    limit: int = Query(default=20, ge=1, le=200),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    states = jobs.list_oldest_queued_jobs(limit=limit)
    records = [
        JobStatusResponse(
            job_id=state.job_id,
            job_type=state.job_type,
            status=state.status,
            created_at=state.created_at,
            updated_at=state.updated_at,
            result=state.result,
            error=state.error,
        )
        for state in states
    ]
    return JobListResponse(total=len(records), records=records)


@app.get("/api/v1/jobs/dead-letter-rate", response_model=JobDeadLetterRateResponse, tags=["Jobs"])
def get_dead_letter_rate(
    window_seconds: float = Query(default=3600.0, ge=1.0),
    threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    rate = cast(
        dict[str, object],
        jobs.get_dead_letter_rate_status(
            window_seconds=window_seconds,
            threshold_per_minute=threshold_per_minute,
        ),
    )
    return JobDeadLetterRateResponse(
        status="success",
        window_seconds=float(cast(float, rate["window_seconds"])),
        threshold_per_minute=float(cast(float, rate["threshold_per_minute"])),
        recent_dead_letter=cast(int, rate["recent_dead_letter"]),
        total_dead_letter=cast(int, rate["total_dead_letter"]),
        rate_per_minute=float(cast(float, rate["rate_per_minute"])),
        breached=bool(rate["breached"]),
    )


@app.get("/api/v1/jobs/dead-letter-top-types", response_model=JobDeadLetterTopTypesResponse, tags=["Jobs"])
def get_dead_letter_top_types(
    limit: int = Query(default=10, ge=1, le=100),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    rows = jobs.get_dead_letter_top_types(limit=limit)
    records = [
        JobDeadLetterTopTypeRecord(
            job_type=str(cast(dict[str, object], row)["job_type"]),
            dead_letter=cast(int, cast(dict[str, object], row)["dead_letter"]),
        )
        for row in rows
    ]
    return JobDeadLetterTopTypesResponse(status="success", records=records)


@app.get("/api/v1/jobs/dead-letter-errors", response_model=JobDeadLetterErrorsResponse, tags=["Jobs"])
def get_dead_letter_error_summary(
    limit: int = Query(default=10, ge=1, le=100),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    rows = jobs.get_dead_letter_error_summary(limit=limit)
    records = [
        JobDeadLetterErrorRecord(
            error_message=str(cast(dict[str, object], row)["error_message"]),
            dead_letter=cast(int, cast(dict[str, object], row)["dead_letter"]),
        )
        for row in rows
    ]
    return JobDeadLetterErrorsResponse(status="success", records=records)


@app.get("/api/v1/jobs/dead-letter-trend", response_model=JobDeadLetterTrendResponse, tags=["Jobs"])
def get_dead_letter_trend(
    window_seconds: float = Query(default=3600.0, ge=1.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    trend = cast(dict[str, object], jobs.get_dead_letter_trend_status(window_seconds=window_seconds))
    return JobDeadLetterTrendResponse(
        status="success",
        window_seconds=float(cast(float, trend["window_seconds"])),
        recent_count=cast(int, trend["recent_count"]),
        previous_count=cast(int, trend["previous_count"]),
        delta=cast(int, trend["delta"]),
        direction=str(trend["direction"]),
    )


@app.get("/api/v1/jobs/dead-letter-recent", response_model=JobListResponse, tags=["Jobs"])
def list_recent_dead_letter_jobs(
    limit: int = Query(default=20, ge=1, le=200),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    states = jobs.list_recent_dead_letter_jobs(limit=limit)
    records = [
        JobStatusResponse(
            job_id=state.job_id,
            job_type=state.job_type,
            status=state.status,
            created_at=state.created_at,
            updated_at=state.updated_at,
            result=state.result,
            error=state.error,
        )
        for state in states
    ]
    return JobListResponse(total=len(records), records=records)


@app.get("/api/v1/jobs/alerts", response_model=JobAlertsSnapshotResponse, tags=["Jobs"])
def get_job_alerts_snapshot(
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    signals_status = cast(
        dict[str, object],
        jobs.get_alert_signals_status(
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    worker = cast(dict[str, object], signals_status["worker"])
    queue_age = cast(dict[str, object], signals_status["queue_age"])
    dead_letter_rate = cast(dict[str, object], signals_status["dead_letter_rate"])
    worker_alive = bool(worker["worker_alive"])
    queue_age_breached = bool(queue_age["breached"])
    dead_letter_rate_breached = bool(dead_letter_rate["breached"])

    return JobAlertsSnapshotResponse(
        status="success",
        severity=str(signals_status["severity"]),
        breached=bool(signals_status["breached"]),
        worker_alive=worker_alive,
        paused=bool(worker["paused"]),
        queued=cast(int, worker["queued"]),
        running=cast(int, worker["running"]),
        queue_age_breached=queue_age_breached,
        dead_letter_rate_breached=dead_letter_rate_breached,
        oldest_queued_age_seconds=cast(float | None, queue_age["oldest_queued_age_seconds"]),
        dead_letter_rate_per_minute=float(cast(float, dead_letter_rate["rate_per_minute"])),
    )


@app.get("/api/v1/jobs/alerts/signals", response_model=JobAlertsSignalsResponse, tags=["Jobs"])
def get_job_alert_signals(
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    status_payload = cast(
        dict[str, object],
        jobs.get_alert_signals_status(
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    signal_rows = cast(list[dict[str, object]], status_payload["signals"])
    records = [
        JobAlertSignalRecord(
            name=str(row["name"]),
            status=str(row["status"]),
            breached=bool(row["breached"]),
            details=cast(dict, row["details"]),
        )
        for row in signal_rows
    ]
    return JobAlertsSignalsResponse(
        status="success",
        severity=str(status_payload["severity"]),
        breached=bool(status_payload["breached"]),
        signals=records,
    )


@app.get("/api/v1/jobs/alerts/failing-signals", response_model=JobAlertsFailingSignalsResponse, tags=["Jobs"])
def get_job_failing_alert_signals(
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    status_payload = cast(
        dict[str, object],
        jobs.get_failing_alert_signals(
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    signal_rows = cast(list[dict[str, object]], status_payload["signals"])
    records = [
        JobFailingAlertSignalRecord(
            name=str(row["name"]),
            status=str(row["status"]),
            breached=bool(row["breached"]),
            details=cast(dict, row["details"]),
            recommendation=str(row["recommendation"]),
        )
        for row in signal_rows
    ]
    return JobAlertsFailingSignalsResponse(
        status="success",
        severity=str(status_payload["severity"]),
        breached=bool(status_payload["breached"]),
        total_signals=cast(int, status_payload["total_signals"]),
        failing_count=cast(int, status_payload["failing_count"]),
        signals=records,
    )


@app.get("/api/v1/jobs/alerts/recommendations", response_model=JobAlertsRecommendationsResponse, tags=["Jobs"])
def get_job_alert_recommendations(
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    signals_status = cast(
        dict[str, object],
        jobs.get_alert_signals_status(
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    worker = cast(dict[str, object], signals_status["worker"])
    queue_age = cast(dict[str, object], signals_status["queue_age"])
    dead_letter_rate = cast(dict[str, object], signals_status["dead_letter_rate"])
    worker_alive = bool(worker["worker_alive"])
    queue_age_breached = bool(queue_age["breached"])
    dead_letter_rate_breached = bool(dead_letter_rate["breached"])

    recommendations: list[str] = []
    if not worker_alive:
        recommendations.append("Run POST /api/v1/jobs/ensure-worker-alive; if still down, run POST /api/v1/jobs/restart-worker.")
    if queue_age_breached:
        recommendations.append("Inspect GET /api/v1/jobs/queued-oldest and reduce backlog via cancel/requeue in controlled batches.")
    if dead_letter_rate_breached:
        recommendations.append("Pause submissions, inspect recent failures, and use dead-letter dry-run before bulk requeue.")
    if not recommendations:
        recommendations.append("No immediate action required; continue routine monitoring.")

    return JobAlertsRecommendationsResponse(
        status="success",
        severity=str(signals_status["severity"]),
        recommendations=recommendations,
    )


@app.get("/api/v1/jobs/alerts/health", response_model=JobAlertsHealthResponse, tags=["Jobs"])
def get_job_alerts_health(
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    fail_on_warning: bool = Query(default=False),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    signals_status = cast(
        dict[str, object],
        jobs.get_alert_signals_status(
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    severity = str(signals_status["severity"])

    healthy = severity == "ok"
    if fail_on_warning:
        healthy = severity == "ok"
    else:
        healthy = severity != "critical"

    return JobAlertsHealthResponse(
        status="success",
        severity=severity,
        healthy=healthy,
        fail_on_warning=fail_on_warning,
    )


@app.get("/api/v1/jobs/alerts/gate", response_model=JobAlertsGateResponse, tags=["Jobs"])
def get_job_alerts_gate(
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    fail_on_warning: bool = Query(default=False),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    gate = cast(
        dict[str, object],
        jobs.get_alert_gate_status(
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
            fail_on_warning=fail_on_warning,
        ),
    )
    return JobAlertsGateResponse(
        status="success",
        severity=str(gate["severity"]),
        breached=bool(gate["breached"]),
        fail_on_warning=bool(gate["fail_on_warning"]),
        pass_gate=bool(gate["pass_gate"]),
        failing_count=cast(int, gate["failing_count"]),
        reasons=cast(list[str], gate["reasons"]),
    )


@app.get("/api/v1/jobs/alerts/gate/check", response_model=JobAlertsGateResponse, tags=["Jobs"])
def check_job_alerts_gate(
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    fail_on_warning: bool = Query(default=False),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    gate = cast(
        dict[str, object],
        jobs.get_alert_gate_status(
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
            fail_on_warning=fail_on_warning,
        ),
    )
    payload = JobAlertsGateResponse(
        status="success",
        severity=str(gate["severity"]),
        breached=bool(gate["breached"]),
        fail_on_warning=bool(gate["fail_on_warning"]),
        pass_gate=bool(gate["pass_gate"]),
        failing_count=cast(int, gate["failing_count"]),
        reasons=cast(list[str], gate["reasons"]),
    )
    if payload.pass_gate:
        return payload

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )


@app.get("/api/v1/jobs/alerts/gate/matrix", response_model=JobAlertsGateMatrixResponse, tags=["Jobs"])
def get_job_alerts_gate_matrix(
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    matrix = cast(
        dict[str, object],
        jobs.get_alert_gate_matrix_status(
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    relaxed = cast(dict[str, object], matrix["relaxed"])
    strict = cast(dict[str, object], matrix["strict"])

    return JobAlertsGateMatrixResponse(
        status="success",
        severity=str(matrix["severity"]),
        breached=bool(matrix["breached"]),
        relaxed=JobAlertsGateModeResult(
            fail_on_warning=bool(relaxed["fail_on_warning"]),
            pass_gate=bool(relaxed["pass_gate"]),
            failing_count=cast(int, relaxed["failing_count"]),
            reasons=cast(list[str], relaxed["reasons"]),
            recommended_status_code=cast(int, relaxed["recommended_status_code"]),
        ),
        strict=JobAlertsGateModeResult(
            fail_on_warning=bool(strict["fail_on_warning"]),
            pass_gate=bool(strict["pass_gate"]),
            failing_count=cast(int, strict["failing_count"]),
            reasons=cast(list[str], strict["reasons"]),
            recommended_status_code=cast(int, strict["recommended_status_code"]),
        ),
    )


@app.get("/api/v1/jobs/alerts/gate/advice", response_model=JobAlertsGateAdviceResponse, tags=["Jobs"])
def get_job_alerts_gate_advice(
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    advice = cast(
        dict[str, object],
        jobs.get_alert_gate_policy_advice(
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    return JobAlertsGateAdviceResponse(
        status="success",
        severity=str(advice["severity"]),
        breached=bool(advice["breached"]),
        strict_pass=bool(advice["strict_pass"]),
        relaxed_pass=bool(advice["relaxed_pass"]),
        recommended_mode=str(advice["recommended_mode"]),
        deployment_allowed=bool(advice["deployment_allowed"]),
        recommended_status_code=cast(int, advice["recommended_status_code"]),
        reasons=cast(list[str], advice["reasons"]),
    )


@app.get("/api/v1/jobs/alerts/gate/advice/check", response_model=JobAlertsGateAdviceResponse, tags=["Jobs"])
def check_job_alerts_gate_advice(
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    advice = cast(
        dict[str, object],
        jobs.get_alert_gate_policy_advice(
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    payload = JobAlertsGateAdviceResponse(
        status="success",
        severity=str(advice["severity"]),
        breached=bool(advice["breached"]),
        strict_pass=bool(advice["strict_pass"]),
        relaxed_pass=bool(advice["relaxed_pass"]),
        recommended_mode=str(advice["recommended_mode"]),
        deployment_allowed=bool(advice["deployment_allowed"]),
        recommended_status_code=cast(int, advice["recommended_status_code"]),
        reasons=cast(list[str], advice["reasons"]),
    )
    if payload.deployment_allowed:
        return payload

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )


@app.get("/api/v1/jobs/alerts/gate/evaluate", response_model=JobAlertsGateEvaluateResponse, tags=["Jobs"])
def get_job_alerts_gate_evaluate(
    mode: str = Query(default="advice", pattern="^(strict|relaxed|advice)$"),
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    evaluation = cast(
        dict[str, object],
        jobs.get_alert_gate_evaluation(
            mode=mode,
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    return JobAlertsGateEvaluateResponse(
        status="success",
        severity=str(evaluation["severity"]),
        breached=bool(evaluation["breached"]),
        mode=str(evaluation["mode"]),
        pass_gate=bool(evaluation["pass_gate"]),
        deployment_allowed=bool(evaluation["deployment_allowed"]),
        recommended_status_code=cast(int, evaluation["recommended_status_code"]),
        reasons=cast(list[str], evaluation["reasons"]),
        effective_fail_on_warning=cast(bool | None, evaluation["effective_fail_on_warning"]),
        recommended_mode=str(evaluation["recommended_mode"]),
    )


@app.get("/api/v1/jobs/alerts/gate/evaluate/check", response_model=JobAlertsGateEvaluateResponse, tags=["Jobs"])
def check_job_alerts_gate_evaluate(
    mode: str = Query(default="advice", pattern="^(strict|relaxed|advice)$"),
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    evaluation = cast(
        dict[str, object],
        jobs.get_alert_gate_evaluation(
            mode=mode,
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    payload = JobAlertsGateEvaluateResponse(
        status="success",
        severity=str(evaluation["severity"]),
        breached=bool(evaluation["breached"]),
        mode=str(evaluation["mode"]),
        pass_gate=bool(evaluation["pass_gate"]),
        deployment_allowed=bool(evaluation["deployment_allowed"]),
        recommended_status_code=cast(int, evaluation["recommended_status_code"]),
        reasons=cast(list[str], evaluation["reasons"]),
        effective_fail_on_warning=cast(bool | None, evaluation["effective_fail_on_warning"]),
        recommended_mode=str(evaluation["recommended_mode"]),
    )
    if payload.pass_gate:
        return payload

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )


@app.get("/api/v1/jobs/alerts/gate/profile", response_model=JobAlertsGateProfileResponse, tags=["Jobs"])
def get_job_alerts_gate_profile(
    profile: str = Query(default="staging", pattern="^(prod|staging|dev)$"),
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    evaluation = cast(
        dict[str, object],
        jobs.get_alert_gate_profile_evaluation(
            profile=profile,
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    return JobAlertsGateProfileResponse(
        status="success",
        profile=str(evaluation["profile"]),
        profile_mode=str(evaluation["profile_mode"]),
        severity=str(evaluation["severity"]),
        breached=bool(evaluation["breached"]),
        mode=str(evaluation["mode"]),
        pass_gate=bool(evaluation["pass_gate"]),
        deployment_allowed=bool(evaluation["deployment_allowed"]),
        recommended_status_code=cast(int, evaluation["recommended_status_code"]),
        reasons=cast(list[str], evaluation["reasons"]),
        effective_fail_on_warning=cast(bool | None, evaluation["effective_fail_on_warning"]),
        recommended_mode=str(evaluation["recommended_mode"]),
    )


@app.get("/api/v1/jobs/alerts/gate/profile/check", response_model=JobAlertsGateProfileResponse, tags=["Jobs"])
def check_job_alerts_gate_profile(
    profile: str = Query(default="staging", pattern="^(prod|staging|dev)$"),
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    evaluation = cast(
        dict[str, object],
        jobs.get_alert_gate_profile_evaluation(
            profile=profile,
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    payload = JobAlertsGateProfileResponse(
        status="success",
        profile=str(evaluation["profile"]),
        profile_mode=str(evaluation["profile_mode"]),
        severity=str(evaluation["severity"]),
        breached=bool(evaluation["breached"]),
        mode=str(evaluation["mode"]),
        pass_gate=bool(evaluation["pass_gate"]),
        deployment_allowed=bool(evaluation["deployment_allowed"]),
        recommended_status_code=cast(int, evaluation["recommended_status_code"]),
        reasons=cast(list[str], evaluation["reasons"]),
        effective_fail_on_warning=cast(bool | None, evaluation["effective_fail_on_warning"]),
        recommended_mode=str(evaluation["recommended_mode"]),
    )
    if payload.pass_gate:
        return payload

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )


@app.get("/api/v1/jobs/alerts/gate/profile/matrix", response_model=JobAlertsGateProfileMatrixResponse, tags=["Jobs"])
def get_job_alerts_gate_profile_matrix(
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    matrix = cast(
        dict[str, object],
        jobs.get_alert_gate_profile_matrix_evaluation(
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    profiles = cast(dict[str, dict[str, object]], matrix["profiles"])
    profile_payload = {
        name: JobAlertsGateProfileResult(
            profile=str(item["profile"]),
            profile_mode=str(item["profile_mode"]),
            severity=str(item["severity"]),
            breached=bool(item["breached"]),
            mode=str(item["mode"]),
            pass_gate=bool(item["pass_gate"]),
            deployment_allowed=bool(item["deployment_allowed"]),
            recommended_status_code=cast(int, item["recommended_status_code"]),
            reasons=cast(list[str], item["reasons"]),
            effective_fail_on_warning=cast(bool | None, item["effective_fail_on_warning"]),
            recommended_mode=str(item["recommended_mode"]),
        )
        for name, item in profiles.items()
    }
    return JobAlertsGateProfileMatrixResponse(
        status="success",
        severity=str(matrix["severity"]),
        breached=bool(matrix["breached"]),
        recommended_profile=str(matrix["recommended_profile"]),
        deployment_allowed=bool(matrix["deployment_allowed"]),
        recommended_status_code=cast(int, matrix["recommended_status_code"]),
        profiles=profile_payload,
    )


@app.get("/api/v1/jobs/alerts/gate/profile/matrix/check", response_model=JobAlertsGateProfileMatrixResponse, tags=["Jobs"])
def check_job_alerts_gate_profile_matrix(
    queue_age_threshold_seconds: float = Query(default=300.0, ge=0.0),
    dead_letter_window_seconds: float = Query(default=3600.0, ge=1.0),
    dead_letter_threshold_per_minute: float = Query(default=1.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    matrix = cast(
        dict[str, object],
        jobs.get_alert_gate_profile_matrix_evaluation(
            queue_age_threshold_seconds=queue_age_threshold_seconds,
            dead_letter_window_seconds=dead_letter_window_seconds,
            dead_letter_threshold_per_minute=dead_letter_threshold_per_minute,
        ),
    )
    profiles = cast(dict[str, dict[str, object]], matrix["profiles"])
    profile_payload = {
        name: JobAlertsGateProfileResult(
            profile=str(item["profile"]),
            profile_mode=str(item["profile_mode"]),
            severity=str(item["severity"]),
            breached=bool(item["breached"]),
            mode=str(item["mode"]),
            pass_gate=bool(item["pass_gate"]),
            deployment_allowed=bool(item["deployment_allowed"]),
            recommended_status_code=cast(int, item["recommended_status_code"]),
            reasons=cast(list[str], item["reasons"]),
            effective_fail_on_warning=cast(bool | None, item["effective_fail_on_warning"]),
            recommended_mode=str(item["recommended_mode"]),
        )
        for name, item in profiles.items()
    }
    payload = JobAlertsGateProfileMatrixResponse(
        status="success",
        severity=str(matrix["severity"]),
        breached=bool(matrix["breached"]),
        recommended_profile=str(matrix["recommended_profile"]),
        deployment_allowed=bool(matrix["deployment_allowed"]),
        recommended_status_code=cast(int, matrix["recommended_status_code"]),
        profiles=profile_payload,
    )
    if payload.deployment_allowed:
        return payload

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )


@app.get("/api/v1/jobs/worker-status", response_model=JobWorkerStatusResponse, tags=["Jobs"])
def get_job_worker_status(
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    worker = cast(dict[str, object], jobs.get_worker_status())
    return JobWorkerStatusResponse(
        status="success",
        worker_alive=bool(worker["worker_alive"]),
        paused=bool(worker["paused"]),
        running=cast(int, worker["running"]),
        queued=cast(int, worker["queued"]),
        drained=bool(worker["drained"]),
    )


@app.post("/api/v1/jobs/restart-worker", response_model=JobWorkerRestartResponse, tags=["Jobs"])
def restart_job_worker(
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    restarted = jobs.restart_worker()
    worker = cast(dict[str, object], jobs.get_worker_status())
    return JobWorkerRestartResponse(
        status="success",
        restarted=bool(restarted),
        worker_alive=bool(worker["worker_alive"]),
        paused=bool(worker["paused"]),
        running=cast(int, worker["running"]),
        queued=cast(int, worker["queued"]),
        drained=bool(worker["drained"]),
    )


@app.post("/api/v1/jobs/ensure-worker-alive", response_model=JobWorkerEnsureResponse, tags=["Jobs"])
def ensure_job_worker_alive(
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    started = jobs.ensure_worker_alive()
    worker = cast(dict[str, object], jobs.get_worker_status())
    return JobWorkerEnsureResponse(
        status="success",
        started=bool(started),
        worker_alive=bool(worker["worker_alive"]),
        paused=bool(worker["paused"]),
        running=cast(int, worker["running"]),
        queued=cast(int, worker["queued"]),
        drained=bool(worker["drained"]),
    )


@app.get("/api/v1/jobs/drain-status", response_model=JobDrainStatusResponse, tags=["Jobs"])
def get_job_drain_status(
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    drain = jobs.get_drain_status()
    typed_drain = cast(dict[str, object], drain)
    running_count = cast(int, typed_drain["running"])
    queued_count = cast(int, typed_drain["queued"])
    return JobDrainStatusResponse(
        status="success",
        paused=bool(typed_drain["paused"]),
        running=running_count,
        queued=queued_count,
        drained=bool(typed_drain["drained"]),
    )


@app.post("/api/v1/jobs/drain-wait", response_model=JobDrainWaitResponse, tags=["Jobs"])
def wait_for_job_drain(
    timeout_seconds: float = Query(default=30.0, ge=0.0, le=300.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    drain = cast(dict[str, object], jobs.wait_for_drain(timeout_seconds=timeout_seconds))
    return JobDrainWaitResponse(
        status="success",
        paused=bool(drain["paused"]),
        running=cast(int, drain["running"]),
        queued=cast(int, drain["queued"]),
        drained=bool(drain["drained"]),
        timed_out=bool(drain["timed_out"]),
        timeout_seconds=float(cast(float, drain["timeout_seconds"])),
    )


@app.post("/api/v1/jobs/pause", response_model=AuthActionResponse, tags=["Jobs"])
def pause_job_processing(
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    jobs.pause_processing()
    return AuthActionResponse(status="success", message="Job processing paused.")


@app.post("/api/v1/jobs/resume", response_model=AuthActionResponse, tags=["Jobs"])
def resume_job_processing(
    require_drained: bool = Query(default=False),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    if require_drained:
        drain = cast(dict[str, object], jobs.get_drain_status())
        if not bool(drain["drained"]):
            raise HTTPException(
                status_code=409,
                detail="Queue is not drained; keep processing paused until running jobs complete.",
            )

    jobs.resume_processing()
    return AuthActionResponse(status="success", message="Job processing resumed.")


@app.post("/api/v1/jobs/resume-safe", response_model=JobSafeResumeResponse, tags=["Jobs"])
def safe_resume_job_processing(
    timeout_seconds: float = Query(default=30.0, ge=0.0, le=300.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    drain = cast(dict[str, object], jobs.wait_for_drain(timeout_seconds=timeout_seconds))
    timed_out = bool(drain["timed_out"])
    drained = bool(drain["drained"])

    resumed = False
    if drained and not timed_out:
        jobs.resume_processing()
        resumed = True

    return JobSafeResumeResponse(
        status="success",
        resumed=resumed,
        paused=bool(drain["paused"]),
        running=cast(int, drain["running"]),
        queued=cast(int, drain["queued"]),
        drained=drained,
        timed_out=timed_out,
        timeout_seconds=float(cast(float, drain["timeout_seconds"])),
    )


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse, tags=["Jobs"])
def get_job_status(
    job_id: str,
    _: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    state = jobs.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return JobStatusResponse(
        job_id=state.job_id,
        job_type=state.job_type,
        status=state.status,
        created_at=state.created_at,
        updated_at=state.updated_at,
        result=state.result,
        error=state.error,
    )


@app.post("/api/v1/jobs/{job_id}/requeue", response_model=JobStatusResponse, tags=["Jobs"])
def requeue_dead_letter_job(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    try:
        state = jobs.requeue_dead_letter(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if state is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return JobStatusResponse(
        job_id=state.job_id,
        job_type=state.job_type,
        status=state.status,
        created_at=state.created_at,
        updated_at=state.updated_at,
        result=state.result,
        error=state.error,
    )


@app.post("/api/v1/jobs/requeue-dead-letter", response_model=JobActionCountResponse, tags=["Jobs"])
def requeue_dead_letter_jobs(
    job_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    dry_run: bool = Query(default=False),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    affected = jobs.requeue_dead_letter_jobs(job_type=job_type, limit=limit, dry_run=dry_run)
    message = "Dead-letter jobs requeued."
    if dry_run:
        message = "Dry-run only: dead-letter jobs eligible for requeue."
    if job_type:
        if dry_run:
            message = f"Dry-run only: dead-letter jobs eligible for requeue for job_type '{job_type}'."
        else:
            message = f"Dead-letter jobs requeued for job_type '{job_type}'."
    return JobActionCountResponse(status="success", message=message, affected_count=affected)


@app.post("/api/v1/jobs/{job_id}/cancel", response_model=JobStatusResponse, tags=["Jobs"])
def cancel_queued_job(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    try:
        state = jobs.cancel_queued_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if state is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return JobStatusResponse(
        job_id=state.job_id,
        job_type=state.job_type,
        status=state.status,
        created_at=state.created_at,
        updated_at=state.updated_at,
        result=state.result,
        error=state.error,
    )


@app.post("/api/v1/jobs/cancel-queued", response_model=JobActionCountResponse, tags=["Jobs"])
def cancel_queued_jobs(
    job_type: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=500),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    affected = jobs.cancel_queued_jobs(job_type=job_type, limit=limit)
    message = "Queued jobs canceled."
    if job_type:
        message = f"Queued jobs canceled for job_type '{job_type}'."
    return JobActionCountResponse(status="success", message=message, affected_count=affected)


@app.post("/api/v1/jobs/cleanup", response_model=JobCleanupResponse, tags=["Jobs"])
def cleanup_terminal_jobs(
    older_than_seconds: float = Query(default=86400.0, ge=0.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    deleted_count = jobs.cleanup_terminal_jobs(older_than_seconds=older_than_seconds)
    return JobCleanupResponse(
        status="success",
        message="Terminal jobs cleanup completed.",
        deleted_count=deleted_count,
    )


@app.post("/api/v1/jobs/recover-stale", response_model=JobCleanupResponse, tags=["Jobs"])
def recover_stale_running_jobs(
    stale_after_seconds: float = Query(default=300.0, ge=1.0),
    current_user: TokenData = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    try:
        require_role(current_user.role, "admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    recovered_count = jobs.recover_stale_running_jobs(stale_after_seconds=stale_after_seconds)
    return JobCleanupResponse(
        status="success",
        message="Stale running job recovery completed.",
        deleted_count=recovered_count,
    )
