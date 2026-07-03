from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DEFAULT_STATUSES, STATUS_MAP


EPS = 1e-9


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0, np.nan).fillna(EPS)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["CLStatusCode"] = out["CLStatusCode"].astype(str).str.upper().str.strip()
    out["CLStatusNumeric"] = out["CLStatusCode"].map(STATUS_MAP).fillna(-1)

    out["ArrearRatio"] = safe_divide(
        out["PrincipalArrear"] + out["InterestArrear"], out["PrincipalOS"]
    )
    out["LTVRatio"] = safe_divide(out["PrincipalOS"], out["SecurityValue"])
    out["InterestStress"] = safe_divide(out["InterestArrear"], out["TotalAccruedInt"])

    if "TotalInstallments" in out.columns:
        out["DefaultedInstRatio"] = safe_divide(out["DefaultedInst"], out["TotalInstallments"])
    else:
        out["DefaultedInstRatio"] = out["DefaultedInst"].astype(float)

    out["AgeDaysBucket"] = pd.cut(
        out["AgeDays"],
        bins=[-np.inf, 30, 90, np.inf],
        labels=["Low", "Medium", "High"],
    )

    out["DelinquencyScore"] = np.select(
        [out["AgeDays"] > 180, out["AgeDays"] > 90, out["AgeDays"] > 30],
        [3, 2, 1],
        default=0,
    )

    out["InstallmentRisk"] = np.select(
        [out["DefaultedInst"] > 5, out["DefaultedInst"] > 2, out["DefaultedInst"] > 0],
        [3, 2, 1],
        default=0,
    )

    if "RepaymentFrequency" not in out.columns:
        out["RepaymentFrequency"] = "Unknown"
    out["RepaymentFrequency"] = out["RepaymentFrequency"].astype(str).str.upper().str.strip()
    out["PaymentFrequencyRiskFlag"] = np.where(out["RepaymentFrequency"].isin(["QUARTERLY", "HALF YEARLY"]), 1, 0)

    out["Sector"] = out["Sector"].astype(str).str.upper().str.strip()
    sector_counts = out["Sector"].value_counts(normalize=True)
    out["SectorRiskScore"] = out["Sector"].map(1.0 - sector_counts).fillna(0.5)

    if "FutureStatusCode" in out.columns:
        future = out["FutureStatusCode"].astype(str).str.upper().str.strip()
        out["WillDefault"] = future.isin(DEFAULT_STATUSES).astype(int)
    else:
        # Fallback: derive label from current CLStatusCode when future labels unavailable
        out["WillDefault"] = out["CLStatusCode"].isin(DEFAULT_STATUSES).astype(int)

    return out
