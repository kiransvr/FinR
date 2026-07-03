"""
Loan Default Risk API — FastAPI application.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from src.application.risk_service import NotFoundError, RiskService
from src.api.auth import (
    TokenData,
    authenticate_user, create_access_token, get_current_user, require_admin,
)
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
risk_service = RiskService(base_dir=BASE_DIR)

app = FastAPI(
    title="Loan Default Risk",
    description="Collection operations, risk scoring, and visit planning for field officers.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
def health():
    return HealthResponse(**risk_service.get_health())


# ── Outputs ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/scored-accounts", response_model=ScoredAccountsResponse, tags=["Outputs"])
def scored_accounts(
    limit: int = 200,
    current_user: TokenData = Depends(get_current_user),
):
    try:
        total, records = risk_service.get_scored_accounts(limit)
        return ScoredAccountsResponse(total=total, records=records)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/v1/top-risky", response_model=ScoredAccountsResponse, tags=["Outputs"])
def top_risky(
    limit: int = 100,
    current_user: TokenData = Depends(get_current_user),
):
    try:
        total, records = risk_service.get_top_risky(limit)
        return ScoredAccountsResponse(total=total, records=records)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/v1/visit-plan", response_model=VisitPlanResponse, tags=["Outputs"])
def visit_plan(current_user: TokenData = Depends(get_current_user)):
    try:
        total, records = risk_service.get_visit_plan()
        return VisitPlanResponse(total=total, records=records)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/v1/officer-kpis", response_model=OfficerKPIResponse, tags=["Outputs"])
def officer_kpis(current_user: TokenData = Depends(get_current_user)):
    try:
        total, records = risk_service.get_officer_kpis()
        return OfficerKPIResponse(total=total, records=records)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/v1/feedback", response_model=FeedbackListResponse, tags=["Feedback"])
def list_feedback(limit: int = 500, current_user: TokenData = Depends(get_current_user)):
    total, records = risk_service.list_feedback(limit)
    return FeedbackListResponse(total=total, records=records)


@app.post("/api/v1/feedback/submit", response_model=FeedbackSubmissionResponse, tags=["Feedback"])
def submit_feedback(body: FeedbackSubmissionRequest, current_user: TokenData = Depends(get_current_user)):
    try:
        feedback_total, saved = risk_service.submit_feedback(
            payload=body.model_dump(),
            recorded_by=current_user.username,
        )
        return FeedbackSubmissionResponse(
            status="success",
            message="Feedback saved successfully.",
            feedback_total=feedback_total,
            record=saved,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Feedback save failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/feedback/refresh-plan", response_model=PlanRefreshResponse, tags=["Feedback"])
def refresh_plan_from_feedback(current_user: TokenData = Depends(require_admin)):
    try:
        visit_rows, kpi_rows, feedback_rows = risk_service.refresh_plan_from_feedback()
        return PlanRefreshResponse(
            status="success",
            message="Visit plan and officer KPIs refreshed from latest feedback.",
            visit_plan_rows=visit_rows,
            officer_kpi_rows=kpi_rows,
            feedback_rows=feedback_rows,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Plan refresh from feedback failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Pipeline trigger ──────────────────────────────────────────────────────────

@app.post("/api/v1/pipeline/run", response_model=PipelineRunResponse, tags=["Pipeline"])
def run_pipeline(current_user: TokenData = Depends(require_admin)):
    """Trigger the full pipeline (admin only). Retrains model and refreshes all outputs."""
    try:
        scored_count, top_risky_count, visit_rows, kpi_rows = risk_service.run_pipeline()
        return PipelineRunResponse(
            status="success",
            message="Pipeline completed successfully.",
            scored_accounts=scored_count,
            top_risky_accounts=top_risky_count,
            visit_plan_rows=visit_rows,
            officer_kpi_rows=kpi_rows,
        )
    except Exception as exc:
        logger.exception("Pipeline run failed")
        raise HTTPException(status_code=500, detail=str(exc))
