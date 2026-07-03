from __future__ import annotations

from pathlib import Path

from src.application.risk_service import RiskService
from src.config import ProjectConfig
from src.infrastructure.output_repository import OutputRepository


def build_risk_service(base_dir: Path) -> RiskService:
    config = ProjectConfig(base_dir=base_dir)
    output_repository = OutputRepository(config)
    return RiskService(base_dir=base_dir, output_store=output_repository)
