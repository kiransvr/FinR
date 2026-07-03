from __future__ import annotations

import re

from src.api.main import app


API_PREFIX = "/api/v1"
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
SUNSET_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def test_openapi_version_follows_semver() -> None:
    schema = app.openapi()
    version = schema.get("info", {}).get("version", "")
    assert SEMVER_PATTERN.fullmatch(version), (
        "OpenAPI info.version must follow semantic versioning (MAJOR.MINOR.PATCH)."
    )


def test_all_public_paths_are_versioned() -> None:
    schema = app.openapi()
    paths = list(schema.get("paths", {}).keys())
    non_versioned_paths = [path for path in paths if not path.startswith(f"{API_PREFIX}/")]
    assert not non_versioned_paths, (
        "All public API paths must be versioned under '/api/v1'. "
        f"Found: {non_versioned_paths}"
    )


def test_deprecated_operations_require_sunset_date_extension() -> None:
    schema = app.openapi()
    invalid_deprecations: list[str] = []

    for path, methods in schema.get("paths", {}).items():
        for method, operation in methods.items():
            if not isinstance(operation, dict):
                continue
            if not operation.get("deprecated", False):
                continue

            sunset = operation.get("x-sunset-date")
            if not isinstance(sunset, str) or not SUNSET_DATE_PATTERN.fullmatch(sunset):
                invalid_deprecations.append(f"{method.upper()} {path}")

    assert not invalid_deprecations, (
        "Deprecated operations must include 'x-sunset-date' in YYYY-MM-DD format. "
        f"Invalid: {invalid_deprecations}"
    )
