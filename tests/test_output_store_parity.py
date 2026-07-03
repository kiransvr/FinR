from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import ProjectConfig
from src.infrastructure.db_output_repository import DbOutputRepository
from src.infrastructure.output_repository import OutputRepository


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_csv_and_db_adapters_return_same_shapes(tmp_path: Path) -> None:
    config = ProjectConfig(base_dir=tmp_path)

    _write_csv(config.scored_output_path, [{"AccountId": "A1", "Risk": 0.8}])
    _write_csv(config.top_risky_output_path, [{"AccountId": "A1", "RiskBand": "High"}])
    _write_csv(config.visit_plan_output_path, [{"OfficerId": "OFF_1", "AccountId": "A1"}])
    _write_csv(config.officer_kpi_output_path, [{"OfficerId": "OFF_1", "AssignedCases": 1}])
    _write_csv(config.field_feedback_log_path, [{"AccountId": "A1", "RecordedAt": "2026-01-01T00:00:00Z"}])
    config.model_output_path.parent.mkdir(parents=True, exist_ok=True)
    config.model_output_path.touch()

    csv_adapter = OutputRepository(config)
    db_adapter = DbOutputRepository(config)

    pairs = [
        (csv_adapter.scored_output_path, db_adapter.scored_output_path),
        (csv_adapter.top_risky_output_path, db_adapter.top_risky_output_path),
        (csv_adapter.visit_plan_output_path, db_adapter.visit_plan_output_path),
        (csv_adapter.officer_kpi_output_path, db_adapter.officer_kpi_output_path),
    ]

    for csv_path, db_path in pairs:
        csv_df = csv_adapter.read_csv(csv_path)
        db_df = db_adapter.read_csv(db_path)
        assert list(csv_df.columns) == list(db_df.columns)

    csv_feedback = csv_adapter.read_feedback_log()
    db_feedback = db_adapter.read_feedback_log()
    assert list(csv_feedback.columns) == list(db_feedback.columns)

    assert csv_adapter.model_exists() == db_adapter.model_exists()


def test_csv_and_db_append_feedback_contract_parity(tmp_path: Path) -> None:
    config = ProjectConfig(base_dir=tmp_path)
    csv_adapter = OutputRepository(config)
    db_adapter = DbOutputRepository(config)

    payload = {
        "AsOfDate": "2026-07-03",
        "OfficerId": "OFF_1",
        "AccountId": "ACC_1",
        "VisitStatus": "Completed",
        "Outcome": "Contacted",
        "PromiseStatus": "None",
        "PromiseToPayDate": "",
        "PromisedAmount": 0.0,
        "ClientHardshipFlag": "No",
        "DisputeFlag": "No",
        "SupervisorEscalation": "No",
        "NextAction": "Follow-up Call",
        "FieldNotes": "parity",
        "RecordedBy": "tester",
    }

    csv_df, csv_saved = csv_adapter.append_feedback(payload)
    db_df, db_saved = db_adapter.append_feedback(payload)

    assert set(csv_df.columns) == set(db_df.columns)
    assert set(csv_saved.keys()) == set(db_saved.keys())
