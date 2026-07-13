from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    elif suffix == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError("Unsupported file format. Use .xlsx, .xls, or .csv")

    df.columns = [str(c).strip() for c in df.columns]
    return df


def validate_columns(df: pd.DataFrame, required_columns: Iterable[str]) -> None:
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned = cleaned.drop_duplicates()

    for col in cleaned.columns:
        if pd.api.types.is_numeric_dtype(cleaned[col]):
            cleaned[col] = cleaned[col].fillna(cleaned[col].median())
        else:
            cleaned[col] = cleaned[col].fillna("Unknown").astype(str).str.strip()

    return cleaned
