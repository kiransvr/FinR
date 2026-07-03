from __future__ import annotations

import numpy as np
import pandas as pd


def apply_rule_score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["RuleScore"] = (
        out["DelinquencyScore"] * 30
        + out["InstallmentRisk"] * 25
        + np.where(out["LTVRatio"] > 0.8, 20, 10)
        + np.where(out["ArrearRatio"] > 0.3, 25, 10)
    )

    out["RuleRiskCategory"] = np.select(
        [out["RuleScore"] >= 70, out["RuleScore"] >= 40],
        ["High Risk", "Medium Risk"],
        default="Low Risk",
    )

    return out
