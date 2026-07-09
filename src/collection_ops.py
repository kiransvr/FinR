from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ID_CANDIDATE_COLUMNS = [
    "LoanAccountNo",
    "LoanAccountNumber",
    "AccountNo",
    "AccountNumber",
    "ClientID",
    "ClientId",
    "CustomerID",
]

FEEDBACK_COLUMNS = [
    "AsOfDate",
    "OfficerId",
    "AccountId",
    "VisitStatus",
    "Outcome",
    "PromiseStatus",
    "PromiseToPayDate",
    "PromisedAmount",
    "ClientHardshipFlag",
    "DisputeFlag",
    "SupervisorEscalation",
    "NextAction",
    "FieldNotes",
    "RecordedBy",
    "RecordedAt",
]


def _pick_first_existing(columns: Iterable[str], candidates: list[str]) -> str | None:
    cols = set(columns)
    for col in candidates:
        if col in cols:
            return col
    return None


def load_feedback_log(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=FEEDBACK_COLUMNS)

    df = pd.read_csv(path)
    for column in FEEDBACK_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df[FEEDBACK_COLUMNS]


def append_feedback_record(path: Path, record: dict) -> tuple[pd.DataFrame, dict]:
    now_ts = pd.Timestamp.now('UTC').strftime("%Y-%m-%dT%H:%M:%SZ")
    canonical = {
        "AsOfDate": str(record.get("AsOfDate", pd.Timestamp.today().strftime("%Y-%m-%d"))),
        "OfficerId": str(record.get("OfficerId", "")).strip(),
        "AccountId": str(record.get("AccountId", "")).strip(),
        "VisitStatus": str(record.get("VisitStatus", "Completed")).strip() or "Completed",
        "Outcome": str(record.get("Outcome", "Contacted")).strip() or "Contacted",
        "PromiseStatus": str(record.get("PromiseStatus", "None")).strip() or "None",
        "PromiseToPayDate": str(record.get("PromiseToPayDate", "")).strip(),
        "PromisedAmount": float(pd.to_numeric(record.get("PromisedAmount", 0), errors="coerce") or 0),
        "ClientHardshipFlag": str(record.get("ClientHardshipFlag", "No")).strip() or "No",
        "DisputeFlag": str(record.get("DisputeFlag", "No")).strip() or "No",
        "SupervisorEscalation": str(record.get("SupervisorEscalation", "No")).strip() or "No",
        "NextAction": str(record.get("NextAction", "Follow-up Call")).strip() or "Follow-up Call",
        "FieldNotes": str(record.get("FieldNotes", "")).strip(),
        "RecordedBy": str(record.get("RecordedBy", "system")).strip() or "system",
        "RecordedAt": str(record.get("RecordedAt", now_ts)).strip() or now_ts,
    }

    if not canonical["AccountId"]:
        raise ValueError("AccountId is required for feedback submission.")

    feedback_df = load_feedback_log(path)
    new_row = pd.DataFrame([canonical], columns=FEEDBACK_COLUMNS)
    if feedback_df.empty:
        feedback_df = new_row
    else:
        feedback_df = pd.concat([feedback_df, new_row], ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    feedback_df.to_csv(path, index=False)
    return feedback_df, canonical


def _normalize_risk_score(df: pd.DataFrame) -> pd.Series:
    if "PredDefaultProbability" in df.columns:
        return df["PredDefaultProbability"].astype(float).clip(0.0, 1.0)
    if "RuleScore" in df.columns:
        rule = df["RuleScore"].astype(float)
        max_rule = float(rule.max()) if not rule.empty else 1.0
        max_rule = max(max_rule, 1.0)
        return (rule / max_rule).clip(0.0, 1.0)
    return pd.Series(np.zeros(len(df), dtype=float), index=df.index)


def _assign_officers(df: pd.DataFrame, officer_pool_size: int = 5) -> pd.Series:
    if "LoanOfficer" in df.columns:
        return df["LoanOfficer"].astype(str).replace("", np.nan).fillna("OFFICER_UNASSIGNED")

    labels = [f"OFFICER_{i}" for i in range(1, officer_pool_size + 1)]
    if "Branch" in df.columns and df["Branch"].notna().any():
        branch_values = df["Branch"].astype(str).fillna("UNKNOWN")
        unique_branches = sorted(branch_values.unique().tolist())
        branch_map = {branch: labels[i % officer_pool_size] for i, branch in enumerate(unique_branches)}
        return branch_values.map(branch_map)

    return pd.Series([labels[i % officer_pool_size] for i in range(len(df))], index=df.index)


def _build_contact_script(days_overdue: float, risk_band: str) -> str:
    if days_overdue <= 7:
        return "Friendly reminder: your installment is due. Please pay today to keep your account current."
    if days_overdue <= 30:
        return "Your account is overdue. Please confirm your payment date today to avoid escalation."
    if risk_band == "High Risk":
        return "Urgent follow-up: your account needs immediate action. Let's agree on a payment plan today."
    return "Please contact us today to regularize your account and avoid further recovery actions."


def _recommended_negotiation(days_overdue: float, installment_risk: float) -> str:
    if days_overdue > 45:
        return "Escalate for supervised rescheduling"
    if days_overdue > 15 or installment_risk >= 2:
        return "Offer partial payment plus dated follow-up"
    return "Standard reminder; no restructuring needed"


def _apply_feedback_adjustments(plan: pd.DataFrame, feedback_log: pd.DataFrame | None) -> pd.DataFrame:
    if feedback_log is None or feedback_log.empty or plan.empty:
        return plan

    feedback = feedback_log.copy()
    if "AccountId" not in feedback.columns:
        return plan

    feedback["RecordedAt"] = pd.to_datetime(feedback.get("RecordedAt"), errors="coerce")
    feedback = feedback.sort_values("RecordedAt", ascending=False)
    latest = feedback.drop_duplicates(subset=["AccountId"], keep="first")

    merged = plan.merge(
        latest[["AccountId", "Outcome", "PromiseStatus", "SupervisorEscalation", "FieldNotes"]],
        on="AccountId",
        how="left",
    )
    merged["Outcome"] = merged["Outcome"].fillna("").astype(str)
    merged["PromiseStatus"] = merged["PromiseStatus"].fillna("").astype(str)
    merged["SupervisorEscalation"] = merged["SupervisorEscalation"].fillna("No").astype(str)

    paid_or_resolved = merged["Outcome"].str.lower().isin(["paid", "resolved", "regularized"])
    broken_promise = merged["PromiseStatus"].str.lower().eq("broken")
    escalated = merged["SupervisorEscalation"].str.lower().eq("yes")

    merged["PriorityScore"] = (
        merged["PriorityScore"]
        + np.where(escalated, 0.2, 0.0)
        + np.where(broken_promise, 0.15, 0.0)
        - np.where(paid_or_resolved, 0.3, 0.0)
    ).clip(0.0, 1.0)

    merged = merged[~paid_or_resolved].copy()
    merged = merged.sort_values(["OfficerId", "PriorityScore"], ascending=[True, False])
    merged["DailyVisitRank"] = merged.groupby("OfficerId")["PriorityScore"].rank(method="first", ascending=False).astype(int)
    return merged


def generate_visit_plan(
    scored_accounts: pd.DataFrame,
    output_path: Path,
    as_of_date: str | None = None,
    feedback_log: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if scored_accounts.empty:
        empty = pd.DataFrame(
            columns=[
                "AsOfDate",
                "OfficerId",
                "AccountId",
                "Branch",
                "DaysOverdue",
                "RiskBand",
                "PriorityScore",
                "ContactChannel",
                "VisitAction",
                "SuggestedNegotiation",
                "SuggestedScript",
                "EscalationFlag",
            ]
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        empty.to_csv(output_path, index=False)
        return empty

    df = scored_accounts.copy()
    df["DaysOverdue"] = pd.to_numeric(df.get("AgeDays", 0), errors="coerce").fillna(0)
    df["InstallmentRisk"] = pd.to_numeric(df.get("InstallmentRisk", 0), errors="coerce").fillna(0)
    df["RiskBand"] = df.get("ModelRiskCategory", df.get("RuleRiskCategory", "Low Risk")).astype(str)
    df["RiskCore"] = _normalize_risk_score(df)

    overdue_boost = np.where(df["DaysOverdue"] > 15, 0.2, 0.0)
    repeat_late_boost = np.where(df["InstallmentRisk"] >= 2, 0.15, 0.0)
    df["PriorityScore"] = (df["RiskCore"] + overdue_boost + repeat_late_boost).clip(0.0, 1.0)

    medium_or_high = df["RiskBand"].isin(["Medium Risk", "High Risk"])
    candidate = df[medium_or_high].copy()
    if candidate.empty:
        candidate = df[df["DaysOverdue"] > 15].copy()

    id_col = _pick_first_existing(candidate.columns, ID_CANDIDATE_COLUMNS)
    if id_col is None:
        candidate["AccountId"] = "ACC_" + candidate.index.astype(str)
    else:
        candidate["AccountId"] = candidate[id_col].astype(str)

    candidate["OfficerId"] = _assign_officers(candidate)
    if "Branch" in candidate.columns:
        candidate["Branch"] = candidate["Branch"].astype(str)
    else:
        candidate["Branch"] = "UNKNOWN"
    candidate["ContactChannel"] = np.where(candidate["DaysOverdue"] <= 7, "SMS", "Call")
    candidate["VisitAction"] = np.where(candidate["DaysOverdue"] > 15, "Field Visit", "Remote Follow-up")
    candidate["SuggestedNegotiation"] = candidate.apply(
        lambda x: _recommended_negotiation(float(x["DaysOverdue"]), float(x["InstallmentRisk"])), axis=1
    )
    candidate["SuggestedScript"] = candidate.apply(
        lambda x: _build_contact_script(float(x["DaysOverdue"]), str(x["RiskBand"])), axis=1
    )
    candidate["EscalationFlag"] = np.where(
        (candidate["DaysOverdue"] > 45) | (candidate["RiskBand"] == "High Risk"), "Yes", "No"
    )

    date_value = as_of_date or pd.Timestamp.today().strftime("%Y-%m-%d")
    candidate["AsOfDate"] = date_value
    candidate = candidate.sort_values(["OfficerId", "PriorityScore"], ascending=[True, False])

    plan = candidate[
        [
            "AsOfDate",
            "OfficerId",
            "AccountId",
            "Branch",
            "DaysOverdue",
            "RiskBand",
            "PriorityScore",
            "ContactChannel",
            "VisitAction",
            "SuggestedNegotiation",
            "SuggestedScript",
            "EscalationFlag",
        ]
    ].copy()
    plan["DailyVisitRank"] = plan.groupby("OfficerId")["PriorityScore"].rank(method="first", ascending=False).astype(int)

    plan = _apply_feedback_adjustments(plan, feedback_log)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plan.to_csv(output_path, index=False)
    return plan


def _coaching_tip(pct_current: float, avg_days_overdue: float, escalations: int) -> str:
    if pct_current < 0.7:
        return "Increase early reminders and same-day callbacks for new overdue cases."
    if avg_days_overdue > 20:
        return "Prioritize repayment-date commitments and shorter revisit cycles."
    if escalations > 5:
        return "Review negotiation quality and involve supervisor earlier on hard cases."
    return "Performance stable. Continue proactive follow-up and documentation quality."


def generate_officer_kpis(visit_plan: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    if visit_plan.empty:
        empty = pd.DataFrame(
            columns=[
                "OfficerId",
                "AssignedCases",
                "HighRiskCases",
                "PctCurrent",
                "AverageDaysOverdue",
                "RescheduleCandidateRate",
                "EscalationCount",
                "CoachingTip",
            ]
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        empty.to_csv(output_path, index=False)
        return empty

    kpi = (
        visit_plan.groupby("OfficerId", as_index=False)
        .agg(
            AssignedCases=("AccountId", "count"),
            HighRiskCases=("RiskBand", lambda s: int((s == "High Risk").sum())),
            AverageDaysOverdue=("DaysOverdue", "mean"),
            RescheduleCandidateRate=(
                "SuggestedNegotiation",
                lambda s: float((s.str.contains("reschedul", case=False, na=False)).mean()),
            ),
            EscalationCount=("EscalationFlag", lambda s: int((s == "Yes").sum())),
        )
        .sort_values("OfficerId")
    )

    kpi["PctCurrent"] = (1.0 - (kpi["AverageDaysOverdue"] / 60.0)).clip(0.0, 1.0)
    kpi["CoachingTip"] = kpi.apply(
        lambda x: _coaching_tip(float(x["PctCurrent"]), float(x["AverageDaysOverdue"]), int(x["EscalationCount"])), axis=1
    )
    kpi["AverageDaysOverdue"] = kpi["AverageDaysOverdue"].round(2)
    kpi["PctCurrent"] = kpi["PctCurrent"].round(3)
    kpi["RescheduleCandidateRate"] = kpi["RescheduleCandidateRate"].round(3)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    kpi.to_csv(output_path, index=False)
    return kpi


def generate_field_feedback_template(output_path: Path) -> None:
    template = pd.DataFrame(
        [
            {
                "AsOfDate": "YYYY-MM-DD",
                "OfficerId": "OFFICER_1",
                "AccountId": "ACC_1001",
                "VisitStatus": "Completed",
                "Outcome": "Contacted",
                "PromiseStatus": "None",
                "PromiseToPayDate": "YYYY-MM-DD",
                "PromisedAmount": 0.0,
                "ClientHardshipFlag": "No",
                "DisputeFlag": "No",
                "SupervisorEscalation": "No",
                "NextAction": "Follow-up Call",
                "FieldNotes": "Customer requested two-day extension due to cash-flow delay.",
                "RecordedBy": "field_officer",
                "RecordedAt": "YYYY-MM-DDTHH:MM:SSZ",
            }
        ]
    )
    for column in FEEDBACK_COLUMNS:
        if column not in template.columns:
            template[column] = ""
    template = template[FEEDBACK_COLUMNS]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    template.to_csv(output_path, index=False)
