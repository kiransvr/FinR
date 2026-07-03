from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd


class OutputStore(Protocol):
    @property
    def scored_output_path(self) -> Path:
        ...

    @property
    def top_risky_output_path(self) -> Path:
        ...

    @property
    def visit_plan_output_path(self) -> Path:
        ...

    @property
    def officer_kpi_output_path(self) -> Path:
        ...

    def model_exists(self) -> bool:
        ...

    def output_exists(self, path: Path) -> bool:
        ...

    def read_csv(self, path: Path) -> pd.DataFrame:
        ...

    def read_feedback_log(self) -> pd.DataFrame:
        ...

    def append_feedback(self, record: dict) -> tuple[pd.DataFrame, dict]:
        ...
