from __future__ import annotations

import os
from pathlib import Path

from src.application.ports import OutputStore
from src.application.risk_service import RiskService
from src.config import ProjectConfig
from src.infrastructure.db_output_repository import DbOutputRepositoryStub
from src.infrastructure.output_repository import OutputRepository


def build_risk_service(base_dir: Path) -> RiskService:
    config = ProjectConfig(base_dir=base_dir)
    adapter = os.getenv("OUTPUT_STORE_ADAPTER", "csv").strip().lower()
    output_repository: OutputStore

    if adapter == "db_stub":
        output_repository = DbOutputRepositoryStub(config)
    elif adapter == "csv":
        output_repository = OutputRepository(config)
    else:
        raise ValueError(f"Unsupported OUTPUT_STORE_ADAPTER '{adapter}'")

    return RiskService(base_dir=base_dir, output_store=output_repository)
