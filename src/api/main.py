"""
Loan Default Risk API — FastAPI application.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

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
from src.collection_ops import append_feedback_record, generate_officer_kpis, generate_visit_plan, load_feedback_log

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = BASE_DIR / "outputs"
MODEL_PATH = BASE_DIR / "models" / "default_risk_model.joblib"
FEEDBACK_LOG_PATH = OUTPUTS_DIR / "field_feedback_log.csv"

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


def _load_csv(filename: str) -> pd.DataFrame:
    path = OUTPUTS_DIR / filename
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


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
    return HealthResponse(
        status="ok",
        model_loaded=MODEL_PATH.exists(),
        pipeline_outputs_available=(OUTPUTS_DIR / "scored_accounts.csv").exists(),
    )


# ── Outputs ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/scored-accounts", response_model=ScoredAccountsResponse, tags=["Outputs"])
def scored_accounts(
    limit: int = 200,
    current_user: TokenData = Depends(get_current_user),
):
    df = _load_csv("scored_accounts.csv")
    if df.empty:
        raise HTTPException(status_code=404, detail="No scored accounts found. Run the pipeline first.")
    records = df.head(limit).fillna("").to_dict(orient="records")
    return ScoredAccountsResponse(total=len(df), records=records)


@app.get("/api/v1/top-risky", response_model=ScoredAccountsResponse, tags=["Outputs"])
def top_risky(
    limit: int = 100,
    current_user: TokenData = Depends(get_current_user),
):
    df = _load_csv("top_risky_accounts.csv")
    if df.empty:
        raise HTTPException(status_code=404, detail="No risky accounts found. Run the pipeline first.")
    records = df.head(limit).fillna("").to_dict(orient="records")
    return ScoredAccountsResponse(total=len(df), records=records)


@app.get("/api/v1/visit-plan", response_model=VisitPlanResponse, tags=["Outputs"])
def visit_plan(current_user: TokenData = Depends(get_current_user)):
    df = _load_csv("daily_visit_plan.csv")
    if df.empty:
        raise HTTPException(status_code=404, detail="No visit plan found. Run the pipeline first.")
    return VisitPlanResponse(total=len(df), records=df.fillna("").to_dict(orient="records"))


@app.get("/api/v1/officer-kpis", response_model=OfficerKPIResponse, tags=["Outputs"])
def officer_kpis(current_user: TokenData = Depends(get_current_user)):
    df = _load_csv("officer_kpis.csv")
    if df.empty:
        raise HTTPException(status_code=404, detail="No KPI data found. Run the pipeline first.")
    return OfficerKPIResponse(total=len(df), records=df.fillna("").to_dict(orient="records"))


@app.get("/api/v1/feedback", response_model=FeedbackListResponse, tags=["Feedback"])
def list_feedback(limit: int = 500, current_user: TokenData = Depends(get_current_user)):
    df = load_feedback_log(FEEDBACK_LOG_PATH)
    if df.empty:
        return FeedbackListResponse(total=0, records=[])
    records = df.sort_values("RecordedAt", ascending=False).head(limit).fillna("").to_dict(orient="records")
    return FeedbackListResponse(total=len(df), records=records)


@app.post("/api/v1/feedback/submit", response_model=FeedbackSubmissionResponse, tags=["Feedback"])
def submit_feedback(body: FeedbackSubmissionRequest, current_user: TokenData = Depends(get_current_user)):
    try:
        feedback_df, saved = append_feedback_record(
            FEEDBACK_LOG_PATH,
            {
                **body.model_dump(),
                "RecordedBy": current_user.username,
            },
        )
        return FeedbackSubmissionResponse(
            status="success",
            message="Feedback saved successfully.",
            feedback_total=len(feedback_df),
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
        scored = _load_csv("scored_accounts.csv")
        if scored.empty:
            raise HTTPException(status_code=404, detail="No scored accounts found. Run the pipeline first.")

        feedback = load_feedback_log(FEEDBACK_LOG_PATH)
        visit = generate_visit_plan(
            scored,
            OUTPUTS_DIR / "daily_visit_plan.csv",
            feedback_log=feedback,
        )
        kpis = generate_officer_kpis(visit, OUTPUTS_DIR / "officer_kpis.csv")
        return PlanRefreshResponse(
            status="success",
            message="Visit plan and officer KPIs refreshed from latest feedback.",
            visit_plan_rows=len(visit),
            officer_kpi_rows=len(kpis),
            feedback_rows=len(feedback),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Plan refresh from feedback failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Pipeline trigger ──────────────────────────────────────────────────────────

@app.post("/api/v1/pipeline/run", response_model=PipelineRunResponse, tags=["Pipeline"])
def run_pipeline(current_user: TokenData = Depends(require_admin)):
    """Trigger the full pipeline (admin only). Retrains model and refreshes all outputs."""
    try:
        from src.pipeline import run
        run(BASE_DIR)
        scored = _load_csv("scored_accounts.csv")
        top_risky = _load_csv("top_risky_accounts.csv")
        visit = _load_csv("daily_visit_plan.csv")
        kpis = _load_csv("officer_kpis.csv")
        return PipelineRunResponse(
            status="success",
            message="Pipeline completed successfully.",
            scored_accounts=len(scored),
            top_risky_accounts=len(top_risky),
            visit_plan_rows=len(visit),
            officer_kpi_rows=len(kpis),
        )
    except Exception as exc:
        logger.exception("Pipeline run failed")
        raise HTTPException(status_code=500, detail=str(exc))
