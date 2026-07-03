from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.application.ports import OutputStore
from src.config import ProjectConfig
from src.infrastructure.output_repository import OutputRepository


class DbOutputRepositoryStub(OutputStore):
    """DB-backed output adapter placeholder.

    This stub mirrors the CSV adapter contract so service and API layers can
    switch adapters without interface changes. Replace internals with real DB
    queries/writes when persistence migration starts.
    """

    def __init__(self, config: ProjectConfig):
        self._delegate = OutputRepository(config)

    @property
    def scored_output_path(self) -> Path:
        return self._delegate.scored_output_path

    @property
    def top_risky_output_path(self) -> Path:
        return self._delegate.top_risky_output_path

    @property
    def visit_plan_output_path(self) -> Path:
        return self._delegate.visit_plan_output_path

    @property
    def officer_kpi_output_path(self) -> Path:
        return self._delegate.officer_kpi_output_path

    def model_exists(self) -> bool:
        return self._delegate.model_exists()

    def output_exists(self, path: Path) -> bool:
        return self._delegate.output_exists(path)

    def read_csv(self, path: Path) -> pd.DataFrame:
        return self._delegate.read_csv(path)

    def read_feedback_log(self) -> pd.DataFrame:
        return self._delegate.read_feedback_log()

    def append_feedback(self, record: dict) -> tuple[pd.DataFrame, dict]:
        return self._delegate.append_feedback(record)
