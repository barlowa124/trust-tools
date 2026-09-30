"""Random Survival Forest wrapper."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sksurv.ensemble import RandomSurvivalForest
from sksurv.util import Surv


def fit_rsf(df: pd.DataFrame, seed: int, duration: str = "os_months",
            event: str = "event") -> RandomSurvivalForest:
    X = df.drop(columns=[duration, event])
    y = Surv.from_dataframe(event, duration, df)
    rsf = RandomSurvivalForest(n_estimators=300, min_samples_leaf=10,
                               random_state=seed, n_jobs=1)
    rsf.fit(X, y)
    return rsf


def rsf_survival(rsf: RandomSurvivalForest, X: pd.DataFrame, times: np.ndarray) -> np.ndarray:
    """Predicted survival matrix (n_samples x len(times)) via step functions."""
    funcs = rsf.predict_survival_function(X)
    out = np.empty((len(funcs), len(times)))
    for i, fn in enumerate(funcs):
        out[i] = fn(times)
    return out


def rsf_risk(rsf: RandomSurvivalForest, X: pd.DataFrame) -> np.ndarray:
    return rsf.predict(X)
