"""
Loan Default Risk API — FastAPI application.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from src.application.access_policy import AuthorizationError, require_role
from src.application.contracts import FeedbackSubmission
from src.application.risk_service import NotFoundError, RiskService
from src.api.auth import (
    TokenData,
    authenticate_user, create_access_token, get_current_user,
)
from src.api.observability import install_observability_middleware
from src.api.schemas import (
    HealthResponse, LoginRequest as SchemaLoginRequest, TokenResponse,
    ScoredAccountsResponse, VisitPlanResponse, OfficerKPIResponse,
    PipelineRunResponse,
    FeedbackSubmissionRequest,
    FeedbackSubmissionResponse,
    FeedbackListResponse,
    PlanRefreshResponse,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
_risk_service = RiskService(base_dir=BASE_DIR)


def get_risk_service() -> RiskService:
    return _risk_service


def _raise_not_found(exc: NotFoundError) -> None:
    raise HTTPException(status_code=404, detail=str(exc))


def _get_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:8501")
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return origins or ["http://localhost:3000", "http://localhost:8501"]

app = FastAPI(
    title="Loan Default Risk",
    description="Collection operations, risk scoring, and visit planning for field officers.",
    version="1.0.0",
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
# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(body: SchemaLoginRequest):
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": user.username, "role": user.role})
    return TokenResponse(access_token=token)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
def health(service: RiskService = Depends(get_risk_service)):
    health_status = service.get_health()
    return HealthResponse(
        status=health_status.status,
        model_loaded=health_status.model_loaded,
        pipeline_outputs_available=health_status.pipeline_outputs_available,
    )


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
