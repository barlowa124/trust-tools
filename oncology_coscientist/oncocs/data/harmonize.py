"""Harmonize raw cohort frames into one row per patient."""
from __future__ import annotations

import numpy as np
import pandas as pd

from oncocs.config import CohortConfig

MISSING_TOKENS = {"", "NA", "N/A", "NaN", "nan", "null", "Not Available",
                  "[Not Available]", "[Not Evaluated]", "[Pending]",
                  "[Discrepancy]", "[Completed]", "unknown"}


def _clean(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    return s.where(~s.isin(MISSING_TOKENS), np.nan)


def harmonize(
    cfg: CohortConfig,
    clinical_patient: pd.DataFrame,
    clinical_sample: pd.DataFrame,
    expression: pd.DataFrame,
    mutations: pd.DataFrame,
    sequenced: set | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return (patient_table, expression_per_patient, report).

    patient_table: one row per patient with os_months, event, covariates, mutation flags.
    expression_per_patient: samples x genes restricted to kept patients (index = patient id).
    report: missingness and drop accounting.
    """
    pid = cfg.patient_id
    report = {"dropped": {}, "missingness": {}, "dropped_covariates": []}

    cp = clinical_patient.copy()
    cs = clinical_sample.copy()

    # --- survival ---
    cp["os_months"] = pd.to_numeric(_clean(cp[cfg.os_months]), errors="coerce")
    deceased_val = cfg.os_status_map.get("deceased", "1:DECEASED")
    living_val = cfg.os_status_map.get("living", "0:LIVING")
    status_clean = _clean(cp[cfg.os_status])
    cp["event"] = np.where(
        status_clean == deceased_val, 1,
        np.where(status_clean == living_val, 0, np.nan))

    n0 = len(cp)
    bad = cp["os_months"].isna() | cp["event"].isna()
    report["dropped"]["missing_os"] = int(bad.sum())
    cp = cp[~bad]
    bad2 = cp["os_months"] <= 0
    report["dropped"]["nonpositive_os_months"] = int(bad2.sum())
    cp = cp[~bad2]
    report["n_patients_with_survival"] = int(len(cp))

    # --- sample linkage: primary tumor only, dedupe to one sample per patient ---
    sample_pid = cfg.columns["sample_patient_id"]
    sid = cfg.columns["sample_id"]
    prim = cs[cs[sid].astype(str).str.endswith(cfg.sample_type_suffix)].copy()
    prim = prim.sort_values(sid)
    dup_counts = prim.groupby(sample_pid).size()
    multi = dup_counts[dup_counts > 1]
    report["dropped"]["extra_primary_samples"] = int((multi - 1).sum())
    report["patients_with_multiple_primary_samples"] = int(len(multi))
    prim = prim.drop_duplicates(subset=[sample_pid], keep="first")
    sample_for_patient = dict(zip(prim[sample_pid], prim[sid], strict=True))

    cp = cp[cp[pid].isin(sample_for_patient)]
    report["dropped"]["no_primary_sample"] = int(
        n0 - report["dropped"]["missing_os"]
        - report["dropped"]["nonpositive_os_months"] - len(cp))
    cp["sample_id"] = cp[pid].map(sample_for_patient)

    # --- covariates ---
    covar_cols = {}
    report["omitted_covariates"] = [k for k, v in cfg.covariates.items() if not v]
    if cfg.covariates.get("age"):
        cp["age"] = pd.to_numeric(_clean(cp[cfg.covariates["age"]]), errors="coerce")
        covar_cols["age"] = "numeric"
    if cfg.covariates.get("sex"):
        cp["sex"] = _clean(cp[cfg.covariates["sex"]])
        covar_cols["sex"] = "categorical"
    if cfg.covariates.get("stage"):
        raw_stage = _clean(cp[cfg.covariates["stage"]])
        cp["stage"] = raw_stage.map(cfg.stage_map)
        covar_cols["stage"] = "categorical"

    # --- mutation flags ---
    mut = mutations.copy()
    gene_col = "Hugo_Symbol" if "Hugo_Symbol" in mut.columns else mut.columns[0]
    sample_col = "Tumor_Sample_Barcode" if "Tumor_Sample_Barcode" in mut.columns else sid
    mut_samples = {g: set(mut.loc[mut[gene_col] == g, sample_col].astype(str))
                   for g in cfg.mutation_genes}
    for g in cfg.mutation_genes:
        cp[f"mut_{g}"] = cp["sample_id"].isin(mut_samples.get(g, set())).astype(float)
        covar_cols[f"mut_{g}"] = "binary"
    if sequenced is not None:
        unseq = ~cp["sample_id"].isin(sequenced)
        report["n_unsequenced_patients"] = int(unseq.sum())
        for g in cfg.mutation_genes:
            cp.loc[unseq, f"mut_{g}"] = np.nan

    # --- missingness report + drop covariates over the configured fraction ---
    for col in list(covar_cols):
        frac = float(cp[col].isna().mean()) if len(cp) else 0.0
        report["missingness"][col] = {"missing": int(cp[col].isna().sum()),
                                      "fraction": round(frac, 4)}
        if frac > cfg.max_missing_fraction:
            report["dropped_covariates"].append(col)
            del covar_cols[col]

    keep = [pid, "sample_id", "os_months", "event"] + sorted(covar_cols)
    patients = cp[keep].set_index(pid).sort_index()

    # --- expression restricted to kept patients ---
    expr_by_sample = expression.copy()
    expr_by_sample.index = expr_by_sample.index.astype(str)
    sample_to_patient = {v: k for k, v in sample_for_patient.items()}
    have = expr_by_sample.index.intersection(sample_to_patient.keys())
    expr_pat = expr_by_sample.loc[have]
    expr_pat.index = [sample_to_patient[s] for s in have]
    expr_pat = expr_pat.reindex(patients.index)

    report["n_patients_final"] = int(len(patients))
    report["n_patients_with_expression"] = int(expr_pat.notna().any(axis=1).sum())
    report["covariates_used"] = covar_cols
    from oncocs.schemas import validate_survival_frame
    validate_survival_frame(patients, cfg)
    return patients, expr_pat, report
