from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.application.contracts import (
    FeedbackSubmission,
    FeedbackSubmitResult,
    HealthStatus,
    PipelineRunResult,
    PlanRefreshResult,
    RecordPage,
)
from src.collection_ops import generate_officer_kpis, generate_visit_plan
from src.config import ProjectConfig
from src.infrastructure.output_repository import OutputRepository


class NotFoundError(Exception):
    pass


class RiskService:
    """Application service orchestrating risk operations and output workflows."""

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        self._config = ProjectConfig(base_dir=base_dir)
        self._repository = OutputRepository(self._config)

    def get_health(self) -> HealthStatus:
        return HealthStatus(
            status="ok",
            model_loaded=self._repository.model_exists(),
            pipeline_outputs_available=self._repository.output_exists(self._repository.scored_output_path),
        )

    def get_scored_accounts(self, limit: int) -> RecordPage:
        df = self._repository.read_csv(self._repository.scored_output_path)
        if df.empty:
            raise NotFoundError("No scored accounts found. Run the pipeline first.")
        records = df.head(limit).fillna("").to_dict(orient="records")
        return RecordPage(total=len(df), records=records)

    def get_top_risky(self, limit: int) -> RecordPage:
        df = self._repository.read_csv(self._repository.top_risky_output_path)
        if df.empty:
            raise NotFoundError("No risky accounts found. Run the pipeline first.")
        records = df.head(limit).fillna("").to_dict(orient="records")
        return RecordPage(total=len(df), records=records)

    def get_visit_plan(self) -> RecordPage:
        df = self._repository.read_csv(self._repository.visit_plan_output_path)
        if df.empty:
            raise NotFoundError("No visit plan found. Run the pipeline first.")
        return RecordPage(total=len(df), records=df.fillna("").to_dict(orient="records"))

    def get_officer_kpis(self) -> RecordPage:
        df = self._repository.read_csv(self._repository.officer_kpi_output_path)
        if df.empty:
            raise NotFoundError("No KPI data found. Run the pipeline first.")
        return RecordPage(total=len(df), records=df.fillna("").to_dict(orient="records"))

    def list_feedback(self, limit: int) -> RecordPage:
        df = self._repository.read_feedback_log()
        if df.empty:
            return RecordPage(total=0, records=[])
        records = df.sort_values("RecordedAt", ascending=False).head(limit).fillna("").to_dict(orient="records")
        return RecordPage(total=len(df), records=records)

    def submit_feedback(self, payload: FeedbackSubmission, recorded_by: str) -> FeedbackSubmitResult:
        feedback_df, saved = self._repository.append_feedback(
            {
                **payload.__dict__,
                "RecordedBy": recorded_by,
            }
        )
        return FeedbackSubmitResult(feedback_total=len(feedback_df), record=saved)

    def refresh_plan_from_feedback(self) -> PlanRefreshResult:
        scored = self._repository.read_csv(self._repository.scored_output_path)
        if scored.empty:
            raise NotFoundError("No scored accounts found. Run the pipeline first.")

        feedback = self._repository.read_feedback_log()
        visit = generate_visit_plan(
            scored,
            self._repository.visit_plan_output_path,
            feedback_log=feedback,
        )
        kpis = generate_officer_kpis(visit, self._repository.officer_kpi_output_path)
        return PlanRefreshResult(
            visit_plan_rows=len(visit),
            officer_kpi_rows=len(kpis),
            feedback_rows=len(feedback),
        )

    def run_pipeline(self) -> PipelineRunResult:
        from src.pipeline import run

        run(self._base_dir)
        scored = self._repository.read_csv(self._repository.scored_output_path)
        top_risky = self._repository.read_csv(self._repository.top_risky_output_path)
        visit = self._repository.read_csv(self._repository.visit_plan_output_path)
        kpis = self._repository.read_csv(self._repository.officer_kpi_output_path)
        return PipelineRunResult(
            scored_accounts=len(scored),
            top_risky_accounts=len(top_risky),
            visit_plan_rows=len(visit),
            officer_kpi_rows=len(kpis),
        )
