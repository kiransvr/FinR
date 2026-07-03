from __future__ import annotations

import os


PRODUCTION_ENV_NAMES = {"production", "prod"}
REQUIRED_PRODUCTION_SETTINGS = (
    "SECRET_KEY",
    "ADMIN_PASSWORD",
    "CORS_ALLOW_ORIGINS",
)


def _is_production() -> bool:
    return os.getenv("APP_ENV", "development").lower() in PRODUCTION_ENV_NAMES


def missing_required_settings() -> list[str]:
    if not _is_production():
        return []
    return [key for key in REQUIRED_PRODUCTION_SETTINGS if not os.getenv(key)]


def enforce_runtime_settings() -> None:
    missing = missing_required_settings()
    if missing:
        raise RuntimeError(
            "Missing required production settings: " + ", ".join(sorted(missing))
        )
