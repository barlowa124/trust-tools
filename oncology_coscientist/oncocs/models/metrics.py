"""Survival metrics: Harrell C, Uno C, time-dependent AUC, IBS, calibration."""
from __future__ import annotations

import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter
from sksurv.metrics import (
    concordance_index_censored,
    concordance_index_ipcw,
    cumulative_dynamic_auc,
    integrated_brier_score,
)
from sksurv.util import Surv


def harrell_c(y_train: Surv, y_test: Surv, risk: np.ndarray) -> float:
    return float(concordance_index_censored(y_test["event"], y_test["time"], risk)[0])


def uno_c(y_train: Surv, y_test: Surv, risk: np.ndarray) -> float:
    return float(concordance_index_ipcw(y_train, y_test, risk)[0])


def td_auc(y_train: Surv, y_test: Surv, risk: np.ndarray,
           eval_months=(12, 24, 36)) -> dict:
    max_t = float(y_test["time"].max())
    times = [t for t in eval_months if t < max_t]
    if not times:
        return {}
    auc, mean_auc = cumulative_dynamic_auc(y_train, y_test, risk, np.array(times))
    out = {f"auc_{int(t)}m": float(a) for t, a in zip(times, auc, strict=True)}
    out["auc_mean"] = float(mean_auc)
    return out


def ibs(y_train: Surv, y_test: Surv, surv: np.ndarray,
        grid_times: np.ndarray, t0=6.0, t1=36.0) -> float:
    """Integrated Brier score over [t0, t1] months (capped by test range)."""
    lo = max(t0, float(y_test["time"].min()))
    hi = min(t1, float(y_test["time"].max()))
    eval_times = np.linspace(lo, hi, 100)
    preds = np.empty((len(y_test), len(eval_times)))
    for j, t in enumerate(eval_times):
        preds[:, j] = surv[:, np.argmin(np.abs(grid_times - t))]
    return float(integrated_brier_score(y_train, y_test, preds, eval_times))


def calibration_24m(y_test: Surv, surv: np.ndarray, grid_times: np.ndarray,
                    t: float = 24.0) -> list:
    """Predicted S(t) deciles vs Kaplan-Meier observed survival per decile."""
    pred = surv[:, np.argmin(np.abs(grid_times - t))]
    if len(np.unique(pred)) < 2:
        kmf = KaplanMeierFitter()
        kmf.fit(np.asarray(y_test["time"], float), np.asarray(y_test["event"], bool))
        return [{"decile": 0, "n": len(pred), "mean_predicted": round(float(pred.mean()), 4),
                 "km_observed": round(float(kmf.predict(t)), 4)}]
    deciles = pd.qcut(pred, 10, labels=False, duplicates="drop")
    rows = []
    for d in sorted(set(deciles)):
        mask = deciles == d
        kmf = KaplanMeierFitter()
        durations = np.asarray(y_test["time"], dtype=float)[np.asarray(mask, dtype=bool)]
        observed = np.asarray(y_test["event"], dtype=bool)[np.asarray(mask, dtype=bool)]
        kmf.fit(durations, observed)
        rows.append({
            "decile": int(d),
            "n": int(mask.sum()),
            "mean_predicted": round(float(pred[mask].mean()), 4),
            "km_observed": round(float(kmf.predict(t)), 4),
        })
    return rows


def evaluate(y_train: Surv, y_test: Surv, risk: np.ndarray,
             surv: np.ndarray, grid_times: np.ndarray) -> dict:
    metrics = {
        "harrell_c": harrell_c(y_train, y_test, risk),
        "uno_c": uno_c(y_train, y_test, risk),
        "integrated_brier_6_36m": ibs(y_train, y_test, surv, grid_times),
        "calibration_24m": calibration_24m(y_test, surv, grid_times),
    }
    metrics.update(td_auc(y_train, y_test, risk))
    return metrics
