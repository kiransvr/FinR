from __future__ import annotations

from pathlib import Path

import pandas as pd

from .collection_ops import (
    generate_field_feedback_template,
    generate_officer_kpis,
    generate_visit_plan,
    load_feedback_log,
)
from .config import ProjectConfig, REQUIRED_COLUMNS
from .data_prep import clean_data, load_data, validate_columns
from .features import engineer_features
from .modeling import score_current_regular_accounts, train_model
from .rule_score import apply_rule_score


def run(base_dir: Path) -> None:
    cfg = ProjectConfig(base_dir=base_dir)

    raw = load_data(cfg.raw_data_path)
    validate_columns(raw, REQUIRED_COLUMNS)

    cleaned = clean_data(raw)
    featured = engineer_features(cleaned)
    scored = apply_rule_score(featured)

    cfg.processed_data_path.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(cfg.processed_data_path, index=False)

    std_rule_scored = scored[scored["CLStatusCode"].astype(str).str.upper() == "STD"].copy()
    std_rule_scored = std_rule_scored.sort_values("RuleScore", ascending=False)

    model_ready = scored["WillDefault"].notna().sum() > 0

    if model_ready:
        model, metrics = train_model(scored, cfg.model_output_path, cfg.metrics_output_path)
        std_model_scored = score_current_regular_accounts(scored, model)

        combined = std_model_scored.merge(
            std_rule_scored[["RuleScore", "RuleRiskCategory"]],
            left_index=True,
            right_index=True,
            how="left",
        )
        combined = combined.sort_values("PredDefaultProbability", ascending=False)
        combined.to_csv(cfg.scored_output_path, index=False)
        combined.head(100).to_csv(cfg.top_risky_output_path, index=False)
        scoring_base = combined

        print("Pipeline complete with ML model.")
        print(f"Processed data: {cfg.processed_data_path}")
        print(f"Scored accounts: {cfg.scored_output_path}")
        print(f"Top risky accounts: {cfg.top_risky_output_path}")
        print(f"Metrics: {cfg.metrics_output_path}")
        print(f"Model: {cfg.model_output_path}")
        print(f"Metrics summary: {metrics}")
    else:
        std_rule_scored.to_csv(cfg.scored_output_path, index=False)
        std_rule_scored.head(100).to_csv(cfg.top_risky_output_path, index=False)
        scoring_base = std_rule_scored

        print("Pipeline complete with rule-based scoring only.")
        print("Reason: No FutureStatusCode labels found for supervised model training.")
        print(f"Processed data: {cfg.processed_data_path}")
        print(f"Scored accounts: {cfg.scored_output_path}")
        print(f"Top risky accounts: {cfg.top_risky_output_path}")

    feedback_log = load_feedback_log(cfg.field_feedback_log_path)
    visit_plan = generate_visit_plan(scoring_base, cfg.visit_plan_output_path, feedback_log=feedback_log)
    officer_kpis = generate_officer_kpis(visit_plan, cfg.officer_kpi_output_path)
    generate_field_feedback_template(cfg.field_feedback_template_path)

    if cfg.field_feedback_log_path.exists() is False:
        feedback_log.to_csv(cfg.field_feedback_log_path, index=False)

    print(f"Daily visit plan: {cfg.visit_plan_output_path}")
    print(f"Officer KPIs: {cfg.officer_kpi_output_path}")
    print(f"Field feedback template: {cfg.field_feedback_template_path}")
    print(f"Feedback log: {cfg.field_feedback_log_path}")
    print(f"Visit plan rows: {len(visit_plan)} | Officer KPI rows: {len(officer_kpis)}")
