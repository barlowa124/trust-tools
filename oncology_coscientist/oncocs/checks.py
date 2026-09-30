"""Run checks. Each returns {name, passed, detail}. A failing check abstains the affected model."""
from __future__ import annotations

import numpy as np
import pandas as pd

from oncocs.splits import split_sha256


def check_split_integrity(split: dict, patient_ids) -> dict:
    recomputed = split_sha256(split["train_ids"], split["test_ids"])
    overlap = set(split["train_ids"]) & set(split["test_ids"])
    data_ids = set(patient_ids)
    missing = sorted((set(split["train_ids"]) | set(split["test_ids"])) - data_ids)
    frac_missing = len(missing) / max(1, len(split["train_ids"]) + len(split["test_ids"]))
    ok = (recomputed == split["split_sha256"] and not overlap and frac_missing <= 0.01)
    return {
        "name": "split_integrity",
        "passed": ok,
        "detail": {
            "hash_match": recomputed == split["split_sha256"],
            "overlap_count": len(overlap),
            "missing_ids": missing,
            "missing_fraction": round(frac_missing, 4),
        },
        "affects": "all",
    }


def check_min_events(train_events: pd.Series, test_events: pd.Series) -> dict:
    tr, te = int(train_events.sum()), int(test_events.sum())
    return {
        "name": "min_events",
        "passed": tr >= 30 and te >= 10,
        "detail": {"train_events": tr, "test_events": te,
                   "required_train": 30, "required_test": 10},
        "affects": "all",
    }


def check_proportional_hazards(cph, train_df: pd.DataFrame) -> dict:
    from lifelines.statistics import proportional_hazard_test
    res = proportional_hazard_test(cph, train_df, time_transform="rank")
    pvals = dict(zip(res.summary.index, res.summary["p"], strict=True))
    offenders = {idx: float(p) for idx, p in pvals.items() if p < 0.01}
    return {
        "name": "proportional_hazards",
        "passed": not offenders,
        "detail": {"covariates_below_p_0.01": offenders,
                   "p_values": {i: float(p) for i, p in pvals.items()}},
        "affects": "cox_clinical",
    }


def check_leakage(train_df: pd.DataFrame, expr_train: pd.DataFrame,
                  feature_cols: dict, n_genes: int,
                  used_gene_cols: list, used_impute: dict, used_scale: dict,
                  excluded_genes: list | tuple = (),
                  excluded_gene_patterns: list | tuple = ()) -> dict:
    """Recompute train-only gene selection, imputation stats, and standardization; compare."""
    detail = {}
    ok = True
    for col, kind in feature_cols.items():
        if kind == "numeric" or kind == "binary":
            rec = float(train_df[col].median()) if train_df[col].notna().any() else 0.0
        elif kind == "categorical":
            modes = train_df[col].mode()
            rec = modes.iloc[0] if len(modes) else None
        else:
            continue
        detail[f"impute_{col}_matches"] = bool(rec == used_impute.get(col))
        ok &= detail[f"impute_{col}_matches"]
    if expr_train is not None and n_genes:
        from oncocs.prep import excluded_gene_set
        drop = excluded_gene_set(expr_train.columns, excluded_genes, excluded_gene_patterns)
        avail = expr_train.drop(columns=drop)
        recomputed_genes = list(avail.var().sort_values(ascending=False).head(n_genes).index)
        detail["gene_selection_matches"] = recomputed_genes == used_gene_cols
        ok &= detail["gene_selection_matches"]
        sub = expr_train[used_gene_cols].copy()
        med = sub.median()
        sub = sub.fillna(med)
        for col in sub.columns:
            rec_mean, rec_sd = float(sub[col].mean()), float(sub[col].std(ddof=1))
            m, s = used_scale.get(col, (np.nan, np.nan))
            detail[f"scale_{col}_matches"] = bool(np.isclose(rec_mean, m) and np.isclose(rec_sd, s))
            ok &= detail[f"scale_{col}_matches"]
    return {"name": "leakage", "passed": ok, "detail": detail, "affects": "all"}


def check_convergence(cph) -> dict:
    conv = bool(np.isfinite(cph.log_likelihood_) and np.isfinite(cph.params_).all())
    return {"name": "convergence", "passed": conv,
            "detail": {"converged": conv, "log_likelihood": float(cph.log_likelihood_)},
            "affects": "cox"}
