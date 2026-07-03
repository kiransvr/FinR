from pathlib import Path


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.name != "__init__.py")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_api_layer_does_not_import_infrastructure_layer() -> None:
    api_root = Path("src/api")
    violating_files: list[str] = []

    for file_path in _python_files(api_root):
        content = _read(file_path)
        if "src.infrastructure" in content or "from ..infrastructure" in content:
            violating_files.append(str(file_path).replace("\\", "/"))

    assert not violating_files, (
        "API layer must not import infrastructure directly. Violations: "
        + ", ".join(violating_files)
    )


def test_application_layer_does_not_import_api_layer() -> None:
    app_root = Path("src/application")
    violating_files: list[str] = []

    for file_path in _python_files(app_root):
        content = _read(file_path)
        if "src.api" in content or "from ..api" in content:
            violating_files.append(str(file_path).replace("\\", "/"))

    assert not violating_files, (
        "Application layer must not import API layer. Violations: "
        + ", ".join(violating_files)
    )
