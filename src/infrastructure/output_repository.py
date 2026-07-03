from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.collection_ops import append_feedback_record, load_feedback_log
from src.config import ProjectConfig


class OutputRepository:
    """Infrastructure adapter for reading and writing output artifacts."""

    def __init__(self, config: ProjectConfig):
        self._config = config

    @property
    def model_path(self) -> Path:
        return self._config.model_output_path

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
    def feedback_log_path(self) -> Path:
        return self._config.field_feedback_log_path

    def model_exists(self) -> bool:
        return self.model_path.exists()

    def output_exists(self, path: Path) -> bool:
        return path.exists()

    def read_csv(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def read_feedback_log(self) -> pd.DataFrame:
        return load_feedback_log(self.feedback_log_path)

    def append_feedback(self, record: dict) -> tuple[pd.DataFrame, dict]:
        return append_feedback_record(self.feedback_log_path, record)
