"""Cox proportional-hazards model wrapper."""
from __future__ import annotations

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter


def fit_cox(df: pd.DataFrame, duration: str = "os_months", event: str = "event") -> CoxPHFitter:
    cph = CoxPHFitter(penalizer=0.1)
    cph.fit(df, duration_col=duration, event_col=event)
    return cph


def cox_summary(cph: CoxPHFitter) -> list:
    s = cph.summary
    return [
        {
            "covariate": idx,
            "hazard_ratio": round(float(np.exp(row["coef"])), 4),
            "hr_ci_lower": round(float(np.exp(row["coef lower 95%"])), 4),
            "hr_ci_upper": round(float(np.exp(row["coef upper 95%"])), 4),
            "p": float(row["p"]),
        }
        for idx, row in s.iterrows()
    ]


def cox_survival(cph: CoxPHFitter, X: pd.DataFrame, times: np.ndarray) -> np.ndarray:
    """Predicted survival matrix (n_samples x len(times))."""
    sf = cph.predict_survival_function(X, times=times)
    return sf.to_numpy().T
