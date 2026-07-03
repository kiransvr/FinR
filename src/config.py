from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectConfig:
    base_dir: Path

    @property
    def default_raw_data_path(self) -> Path:
        return self.base_dir / "data" / "raw" / "Loan Accounts-Dummy.csv"

    @property
    def active_raw_data_path(self) -> Path:
        return self.base_dir / "data" / "raw" / "Loan Accounts-Active.csv"

    @property
    def raw_data_path(self) -> Path:
        if self.active_raw_data_path.exists():
            return self.active_raw_data_path
        return self.default_raw_data_path

    @property
    def processed_data_path(self) -> Path:
        return self.base_dir / "data" / "processed" / "loan_accounts_processed.csv"

    @property
    def scored_output_path(self) -> Path:
        return self.base_dir / "outputs" / "scored_accounts.csv"

    @property
    def top_risky_output_path(self) -> Path:
        return self.base_dir / "outputs" / "top_risky_accounts.csv"

    @property
    def metrics_output_path(self) -> Path:
        return self.base_dir / "outputs" / "model_metrics.json"

    @property
    def model_output_path(self) -> Path:
        return self.base_dir / "models" / "default_risk_model.joblib"

    @property
    def visit_plan_output_path(self) -> Path:
        return self.base_dir / "outputs" / "daily_visit_plan.csv"

    @property
    def officer_kpi_output_path(self) -> Path:
        return self.base_dir / "outputs" / "officer_kpis.csv"

    @property
    def field_feedback_template_path(self) -> Path:
        return self.base_dir / "outputs" / "field_feedback_template.csv"

    @property
    def field_feedback_log_path(self) -> Path:
        return self.base_dir / "outputs" / "field_feedback_log.csv"


STATUS_MAP = {
    "STD": 0,
    "WCH": 1,
    "SUB": 2,
    "DBT": 3,
    "LOS": 4,
}

DEFAULT_STATUSES = {"SUB", "DBT", "LOS"}

REQUIRED_COLUMNS = [
    "CLStatusCode",
    "AgeDays",
    "DefaultedInst",
    "PrincipalOS",
    "PrincipalArrear",
    "InterestArrear",
    "TotalAccruedInt",
    "SecurityValue",
    "Sector",
]

OPTIONAL_COLUMNS = [
    "RepaymentFrequency",
    "TotalInstallments",
    "FutureStatusCode",
    "Branch",
    "SanctionedAmount",
    "IntRate",
]
