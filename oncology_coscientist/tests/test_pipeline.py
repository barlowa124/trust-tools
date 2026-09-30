"""Offline tests on the synthetic cohort fixture."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from sksurv.util import Surv

from oncocs import checks, evidence
from oncocs.cli import main
from oncocs.config import load_cohort
from oncocs.data.harmonize import harmonize
from oncocs.data.load import (
    load_clinical_patient,
    load_clinical_sample,
    load_expression,
    load_mutations,
)
from oncocs.models.metrics import evaluate
from oncocs.splits import load_split, make_split, split_sha256

SEED = 20240601


def _patients(root):
    cfg = load_cohort("synth", root)
    return harmonize(cfg, load_clinical_patient(cfg, root), load_clinical_sample(cfg, root),
                     load_expression(cfg, root), load_mutations(cfg, root))


def _run(root, seed=SEED):
    main(["--data-dir", str(root), "run", "--cohort", "synth", "--seed", str(seed)])
    runs = (root / "results" / "synth").iterdir()
    latest = max(runs, key=lambda p: p.stat().st_mtime)
    return json.loads((latest / "results.json").read_text())


# ---------- split ----------

def test_split_deterministic_and_stratified(synth_root):
    cfg = load_cohort("synth", synth_root)
    patients, _, _ = _patients(synth_root)
    manifest = {"manifest_sha256": "x" * 64}
    s1 = make_split(patients, cfg, SEED, 0.3, manifest["manifest_sha256"], synth_root)
    s2 = make_split(patients, cfg, SEED, 0.3, manifest["manifest_sha256"], synth_root / "other")
    assert s1["train_ids"] == s2["train_ids"] and s1["test_ids"] == s2["test_ids"]
    assert s1["split_sha256"] == s2["split_sha256"]
    ev = patients["event"]
    assert abs(ev[s1["train_ids"]].mean() - ev[s1["test_ids"]].mean()) < 0.05


def test_split_refuses_overwrite_and_supersedes(synth_split):
    cfg = load_cohort("synth", synth_split)
    patients, _, _ = _patients(synth_split)
    with pytest.raises(FileExistsError):
        make_split(patients, cfg, SEED, 0.3, "y" * 64, synth_split)
    old = load_split(cfg, synth_split)["split_sha256"]
    new = make_split(patients, cfg, SEED + 1, 0.3, "y" * 64, synth_split, force=True)
    assert new["supersedes"] == old
    assert new["split_sha256"] != old
    # hash changes if ids change
    assert split_sha256(new["train_ids"][:-1], new["test_ids"]) != new["split_sha256"]


# ---------- harmonize ----------

def test_harmonize_dedup_and_parsing(synth_root):
    patients, expr, report = _patients(synth_root)
    assert patients.index.is_unique
    assert report["dropped"]["extra_primary_samples"] == 1
    assert set(patients["event"].unique()) <= {0, 1}
    assert (patients["os_months"] > 0).all()
    assert patients["stage"].isin(["I", "II", "III", "IV"]).all()
    assert "age" in report["covariates_used"]
    assert expr.shape[0] == len(patients)


def test_missing_covariate_dropped_over_20pct(tmp_path):
    from tests.conftest import _make_cohort_dir
    root = _make_cohort_dir(tmp_path)
    cfg = load_cohort("synth", root)
    cp = load_clinical_patient(cfg, root)
    # blank out 30% of SEX values
    cp.loc[cp.sample(frac=0.3, random_state=1).index, "SEX"] = ""
    patients, _, report = harmonize(cfg, cp, load_clinical_sample(cfg, root),
                                    load_expression(cfg, root), load_mutations(cfg, root))
    assert "sex" in report["dropped_covariates"]
    assert "sex" not in patients.columns


def test_reference_levels_and_mode_imputation(tmp_path):
    from oncocs.prep import prepare_features
    from tests.conftest import _make_cohort_dir
    root = _make_cohort_dir(tmp_path)
    cfg = load_cohort("synth", root)
    cp = load_clinical_patient(cfg, root)
    cp.loc[cp.sample(frac=0.1, random_state=2).index, "SEX"] = ""  # below 20% drop
    patients, expr, report = harmonize(cfg, cp, load_clinical_sample(cfg, root),
                                       load_expression(cfg, root), load_mutations(cfg, root))
    train = patients.index[:200].tolist()
    test = patients.index[200:].tolist()
    X_tr, _, meta = prepare_features(patients, expr, train, test,
                                     report["covariates_used"], 0, False)
    stage_cats = sorted(patients.loc[train, "stage"].dropna().unique())
    sex_cats = sorted(patients.loc[train, "sex"].dropna().unique())
    assert meta["reference_levels"]["stage"] == stage_cats[0]
    assert meta["reference_levels"]["sex"] == sex_cats[0]
    assert sorted(c for c in X_tr.columns if c.startswith("sex_")) == \
        [f"sex_{c}" for c in sex_cats[1:]]
    assert sorted(c for c in X_tr.columns if c.startswith("stage_")) == \
        [f"stage_{c}" for c in stage_cats[1:]]
    mode = patients.loc[train, "sex"].mode().iloc[0]
    assert meta["impute"]["sex"] == mode
    missing_idx = patients.loc[train].index[patients.loc[train, "sex"].isna()]
    assert len(missing_idx) > 0
    for c in sex_cats[1:]:
        assert (X_tr.loc[missing_idx, f"sex_{c}"] == float(c == mode)).all()


def test_unsequenced_samples_get_nan_flags(synth_root):
    cfg = load_cohort("synth", synth_root)
    cs = load_clinical_sample(cfg, synth_root)
    patients, _, _ = _patients(synth_root)
    kept_sample = patients["sample_id"].iloc[0]
    seq = set(cs["SAMPLE_ID"]) - {kept_sample}
    patients2, _, report = harmonize(
        cfg, load_clinical_patient(cfg, synth_root), cs,
        load_expression(cfg, synth_root), load_mutations(cfg, synth_root),
        sequenced=seq)
    pid = patients.index[0]
    assert pd.isna(patients2.loc[pid, "mut_TP53"])
    assert report["n_unsequenced_patients"] == 1
    assert report["missingness"]["mut_TP53"]["missing"] >= 1


def test_excluded_genes_never_selected(synth_root):
    from oncocs.prep import prepare_features
    patients, expr, report = _patients(synth_root)
    expr = expr.copy()
    expr["XIST"] = np.random.default_rng(0).normal(8, 50, len(expr))  # max variance
    train = patients.index[:200].tolist()
    test = patients.index[200:].tolist()
    _, _, meta = prepare_features(patients, expr, train, test,
                                  report["covariates_used"], 50, True,
                                  excluded_genes=["XIST"])
    assert "XIST" not in meta["gene_cols"]
    res = checks.check_leakage(patients.loc[train], expr.loc[train],
                               report["covariates_used"], 50,
                               meta["gene_cols"], meta["impute"], meta["scale"],
                               excluded_genes=["XIST"])
    assert res["passed"]
    # regex patterns are honored too
    _, _, meta2 = prepare_features(patients, expr, train, test,
                                   report["covariates_used"], 50, True,
                                   excluded_gene_patterns=["^XIST$"])
    assert "XIST" not in meta2["gene_cols"]


# ---------- checks ----------

def test_leakage_catches_overlap_and_global_gene_selection(synth_root):
    patients, expr, report = _patients(synth_root)
    kinds = report["covariates_used"]
    train = patients.index[:200].tolist()
    test = patients.index[200:].tolist()
    from oncocs.prep import prepare_features
    _, _, meta = prepare_features(patients, expr, train, test, kinds, 50, True)
    # clean call passes
    res = checks.check_leakage(patients.loc[train], expr.loc[train], kinds, 50,
                               meta["gene_cols"], meta["impute"], meta["scale"])
    assert res["passed"]
    # planted: gene selection computed on ALL data
    bad_genes = list(expr.var().sort_values(ascending=False).head(50).index)
    res = checks.check_leakage(patients.loc[train], expr.loc[train], kinds, 50,
                               bad_genes, meta["impute"], meta["scale"])
    assert not res["passed"]
    # planted: overlap in split ids -> split_integrity fails
    split = {"train_ids": train + [test[0]], "test_ids": test, "split_sha256": ""}
    res = checks.check_split_integrity(split, patients.index)
    assert not res["passed"] and res["detail"]["overlap_count"] == 1


def test_min_events_abstention(synth_root):
    res = checks.check_min_events(pd.Series([1] * 10), pd.Series([1] * 5))
    assert not res["passed"]
    res = checks.check_min_events(pd.Series([1] * 40), pd.Series([1] * 15))
    assert res["passed"]


def test_ph_check_flags_time_varying():
    from lifelines import CoxPHFitter
    rng = np.random.default_rng(0)
    n = 400
    z = rng.binomial(1, 0.5, n)
    # compliant covariate: constant hazard ratio
    t_ok = 30 * (-np.log(rng.uniform(size=n)) / np.exp(0.5 * z)) ** (1 / 1.3)
    df_ok = pd.DataFrame({"z": z, "os_months": np.clip(t_ok, 0.5, 60),
                          "event": (t_ok <= 60).astype(int)})
    cph = CoxPHFitter(penalizer=0.1).fit(df_ok, "os_months", "event")
    assert checks.check_proportional_hazards(cph, df_ok)["passed"]
    # time-varying effect: z protective early, harmful late (crossing hazards)
    t_bad = np.where(z == 0,
                     60 * (-np.log(rng.uniform(size=n))) ** (1 / 0.5),
                     10 * (-np.log(rng.uniform(size=n))) ** (1 / 3))
    df_bad = pd.DataFrame({"z": z, "os_months": np.clip(t_bad, 0.5, 80),
                           "event": (t_bad <= 80).astype(int)})
    cph = CoxPHFitter(penalizer=0.1).fit(df_bad, "os_months", "event")
    assert not checks.check_proportional_hazards(cph, df_bad)["passed"]


# ---------- metrics ----------

def test_metrics_sanity():
    rng = np.random.default_rng(1)
    n = 200
    times = rng.uniform(1, 50, n)
    events = rng.binomial(1, 0.7, n).astype(bool)
    y = Surv.from_arrays(events, times)
    assert checks  # silence unused
    from oncocs.models.metrics import harrell_c
    assert harrell_c(y, y, -times) == pytest.approx(1.0, abs=0.02)
    assert harrell_c(y, y, np.ones(n)) == pytest.approx(0.5)
    grid = np.linspace(0, 50, 50)
    surv = np.tile(np.linspace(1, 0.2, 50), (n, 1))
    m = evaluate(y, y, -times, surv, grid)
    for k in ("harrell_c", "uno_c", "integrated_brier_6_36m"):
        assert 0.0 <= m[k] <= 1.0
    assert m["calibration_24m"]


# ---------- run / abstention / determinism / verify ----------

def test_run_determinism(synth_split):
    r1 = _run(synth_split)
    r2 = _run(synth_split)
    assert evidence.strip_volatile(r1) == evidence.strip_volatile(r2)
    assert r1["run_id"] != r2["run_id"]


def test_abstention_on_min_events(tmp_path):
    from tests.conftest import _make_cohort_dir
    root = _make_cohort_dir(tmp_path, n=40, seed=3)
    cfg = load_cohort("synth", root)
    patients, _, _ = _patients(root)
    make_split(patients, cfg, SEED, 0.3, "z" * 64, root)
    r = _run(root)
    min_ev = next(c for c in r["checks"] if c["name"] == "min_events")
    assert not min_ev["passed"]
    assert all(out["metrics"].get("abstained") for out in r["models"].values())


def test_cli_verify_passes(synth_split, capsys):
    r = _run(synth_split)
    path = synth_split / "results" / "synth" / r["run_id"] / "results.json"
    rc = main(["--data-dir", str(synth_split), "verify", str(path)])
    assert rc == 0


def test_cli_verify_detects_tamper(synth_split, tmp_path):
    r = _run(synth_split)
    path = synth_split / "results" / "synth" / r["run_id"] / "results.json"
    tampered = json.loads(path.read_text())
    tampered["split_sha256"] = "0" * 64
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(tampered))
    assert main(["--data-dir", str(synth_split), "verify", str(bad)]) == 1
