from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.application.ports import OutputStore
from src.collection_ops import FEEDBACK_COLUMNS
from src.config import ProjectConfig


class DbOutputRepository(OutputStore):
    """DB-backed output adapter.

    Uses SQL storage for output tables and feedback logs. For transition safety,
    it can bootstrap table contents from existing CSV files on first read.
    """

    def __init__(self, config: ProjectConfig):
        self._config = config
        self._engine = self._build_engine()

    def _build_engine(self) -> Engine:
        configured = os.getenv("DB_OUTPUT_DATABASE_URL", "").strip()
        if configured:
            return create_engine(configured, future=True)

        db_path = self._config.base_dir / "outputs" / "output_store.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(f"sqlite:///{db_path.as_posix()}", future=True)

    def _table_for_path(self, path: Path) -> str:
        mapping = {
            self.scored_output_path: "scored_accounts",
            self.top_risky_output_path: "top_risky_accounts",
            self.visit_plan_output_path: "daily_visit_plan",
            self.officer_kpi_output_path: "officer_kpis",
        }
        return mapping[path]

    def _table_exists(self, table_name: str) -> bool:
        query = text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = :name"
        )
        with self._engine.connect() as conn:
            row = conn.execute(query, {"name": table_name}).first()
        return row is not None

    def _table_has_rows(self, table_name: str) -> bool:
        if not self._table_exists(table_name):
            return False
        query = text(f"SELECT COUNT(1) AS total FROM {table_name}")
        with self._engine.connect() as conn:
            total = int(conn.execute(query).scalar_one())
        return total > 0

    def _bootstrap_from_csv_if_needed(self, path: Path) -> None:
        table_name = self._table_for_path(path)
        if self._table_has_rows(table_name):
            return
        if not path.exists():
            return

        df = pd.read_csv(path)
        if df.empty:
            return

        with self._engine.begin() as conn:
            df.to_sql(table_name, conn, if_exists="replace", index=False)

    def _canonical_feedback(self, record: dict) -> dict:
        now_ts = pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
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
        return canonical

    @property
    def scored_output_path(self) -> Path:
        return self._config.scored_output_path

    @property
    def top_risky_output_path(self) -> Path:
        return self._config.top_risky_output_path

    @property
    def visit_plan_output_path(self) -> Path:
        return self._config.visit_plan_output_path

    @property
    def officer_kpi_output_path(self) -> Path:
        return self._config.officer_kpi_output_path

    @property
    def model_path(self) -> Path:
        return self._config.model_output_path

    def model_exists(self) -> bool:
        return self.model_path.exists()

    def output_exists(self, path: Path) -> bool:
        table_name = self._table_for_path(path)
        if self._table_has_rows(table_name):
            return True
        return path.exists()

    def read_csv(self, path: Path) -> pd.DataFrame:
        table_name = self._table_for_path(path)
        self._bootstrap_from_csv_if_needed(path)
        if not self._table_exists(table_name):
            return pd.DataFrame()
        query = text(f"SELECT * FROM {table_name}")
        return pd.read_sql_query(query, self._engine)

    def read_feedback_log(self) -> pd.DataFrame:
        table_name = "field_feedback_log"
        if not self._table_exists(table_name):
            return pd.DataFrame(columns=FEEDBACK_COLUMNS)
        query = text(f"SELECT * FROM {table_name}")
        df = pd.read_sql_query(query, self._engine)
        for column in FEEDBACK_COLUMNS:
            if column not in df.columns:
                df[column] = ""
        return df[FEEDBACK_COLUMNS]

    def append_feedback(self, record: dict) -> tuple[pd.DataFrame, dict]:
        canonical = self._canonical_feedback(record)
        row_df = pd.DataFrame([canonical], columns=FEEDBACK_COLUMNS)
        with self._engine.begin() as conn:
            row_df.to_sql("field_feedback_log", conn, if_exists="append", index=False)
        return self.read_feedback_log(), canonical


class DbOutputRepositoryStub(DbOutputRepository):
    """Compatibility alias for legacy adapter name `db_stub`."""
