from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


FEATURE_COLUMNS = [
    "AgeDays",
    "DefaultedInst",
    "PrincipalOS",
    "PrincipalArrear",
    "InterestArrear",
    "TotalAccruedInt",
    "ArrearRatio",
    "LTVRatio",
    "InterestStress",
    "DefaultedInstRatio",
    "DelinquencyScore",
    "InstallmentRisk",
    "PaymentFrequencyRiskFlag",
    "SectorRiskScore",
    "Sector",
    "RepaymentFrequency",
]


def _build_pipeline(numeric_cols: list[str], categorical_cols: list[str]) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_cols,
            ),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_cols,
            ),
        ]
    )

    model = LogisticRegression(max_iter=2000, class_weight="balanced")

    return Pipeline(steps=[("preprocessor", preprocessor), ("model", model)])


def train_model(df: pd.DataFrame, model_path: Path, metrics_path: Path) -> Tuple[Pipeline, Dict[str, float]]:
    train_df = df.dropna(subset=["WillDefault"]).copy()
    train_df["WillDefault"] = train_df["WillDefault"].astype(int)

    missing = [c for c in FEATURE_COLUMNS if c not in train_df.columns]
    if missing:
        raise ValueError(f"Missing feature columns for training: {missing}")

    X = train_df[FEATURE_COLUMNS]
    y = train_df["WillDefault"]

    if y.nunique() < 2:
        raise ValueError("Target needs at least two classes to train a classifier.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )

    numeric_cols = [c for c in FEATURE_COLUMNS if pd.api.types.is_numeric_dtype(X[c])]
    categorical_cols = [c for c in FEATURE_COLUMNS if not pd.api.types.is_numeric_dtype(X[c])]

    pipe = _build_pipeline(numeric_cols, categorical_cols)
    pipe.fit(X_train, y_train)

    preds = pipe.predict(X_test)
    probs = pipe.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_test, preds)),
        "precision": float(precision_score(y_test, preds, zero_division=0)),
        "recall": float(recall_score(y_test, preds, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probs)),
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    return pipe, metrics


def score_current_regular_accounts(df: pd.DataFrame, model: Pipeline) -> pd.DataFrame:
    std_df = df[df["CLStatusCode"].astype(str).str.upper() == "STD"].copy()
    if std_df.empty:
        return std_df

    std_df["PredDefaultProbability"] = model.predict_proba(std_df[FEATURE_COLUMNS])[:, 1]
    std_df["ModelRiskCategory"] = pd.cut(
        std_df["PredDefaultProbability"],
        bins=[-0.01, 0.4, 0.7, 1.0],
        labels=["Low Risk", "Medium Risk", "High Risk"],
    )
    return std_df
