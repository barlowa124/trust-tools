"""Synthetic Weibull-survival cohort fixture written in cBioPortal-like layout."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml


def _make_cohort_dir(root: Path, n: int = 300, seed: int = 7) -> Path:
    rng = np.random.default_rng(seed)
    (root / "cohorts").mkdir(parents=True, exist_ok=True)
    raw = root / "data" / "synth" / "raw"
    raw.mkdir(parents=True, exist_ok=True)

    pids = [f"TCGA-SYN-{i:04d}" for i in range(n)]
    age = rng.normal(65, 10, n).round(1)
    sex = rng.choice(["Male", "Female"], n)
    stage = rng.choice(["STAGE I", "STAGE II", "STAGE IIIA", "STAGE IV"], n)
    stage_risk = np.array(
        [{"STAGE I": 0.0, "STAGE II": 0.2, "STAGE IIIA": 0.4,
          "STAGE IV": 0.7}[s] for s in stage])
    marker = rng.binomial(1, 0.3, n)

    # Weibull survival: marker harmful, higher stage harmful, age mildly harmful
    linpred = 0.01 * (age - 65) + 0.5 * marker + stage_risk
    scale = 40.0
    true_times = (scale * (-np.log(rng.uniform(size=n)) / np.exp(linpred))
                  ** (1 / 1.2) * rng.lognormal(0, 0.6, n))
    censor = rng.uniform(8, 60, n)
    observed = np.minimum(true_times, censor)
    event = (true_times <= censor).astype(int)
    # keep a guaranteed minimum event count
    if event.sum() < n // 3:
        event[rng.choice(n, n // 3, replace=False)] = 1
        observed[event == 1] = np.minimum(observed[event == 1], 40)

    # clinical patient file with # comment headers
    cp = pd.DataFrame({
        "PATIENT_ID": pids, "OS_MONTHS": np.round(observed, 2),
        "OS_STATUS": np.where(event, "1:DECEASED", "0:LIVING"),
        "AGE": age, "SEX": sex, "AJCC_PATHOLOGIC_TUMOR_STAGE": stage,
    })
    hdr = "# synthetic\n# fixture\n# for tests\n# cols\n"
    (raw / "data_clinical_patient.txt").write_text(hdr + cp.to_csv(sep="\t", index=False))

    # clinical sample: patient 0001 gets two primary samples to exercise dedup
    sids = [f"{p}-01" for p in pids]
    extra = pd.DataFrame({"SAMPLE_ID": [f"{pids[0]}-01"], "PATIENT_ID": [pids[0]]})
    cs = pd.concat([pd.DataFrame({"SAMPLE_ID": sids, "PATIENT_ID": pids}), extra])
    (raw / "data_clinical_sample.txt").write_text(hdr + cs.to_csv(sep="\t", index=False))

    # expression: genes x samples, 200 genes; gene_0..4 correlate with marker
    genes = [f"GENE{i}" for i in range(200)]
    expr = rng.normal(8, 1.5, (200, len(sids)))
    expr[:5] += marker[:, None].T if False else marker[None, :]  # marker-linked signal
    expr_df = pd.DataFrame(expr, index=genes, columns=sids)
    expr_df.index.name = "Hugo_Symbol"
    expr_df.to_csv(raw / "data_mrna_seq_v2_rsem.txt", sep="\t")

    mut = pd.DataFrame({
        "Hugo_Symbol": ["TP53"] * 60 + ["KRAS"] * 30,
        "Tumor_Sample_Barcode": list(rng.choice(sids, 60)) + list(rng.choice(sids, 30)),
    })
    (raw / "data_mutations.txt").write_text(mut.to_csv(sep="\t", index=False))

    manifest = {"cohort": "synth", "archive_url": "synthetic://fixture",
                "archive_sha256": "0" * 64, "members": {}}
    for f in raw.iterdir():
        manifest["members"][f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    canon = json.dumps(manifest, sort_keys=True).encode()
    manifest["manifest_sha256"] = hashlib.sha256(canon).hexdigest()
    (root / "data" / "synth" / "manifest.json").write_text(json.dumps(manifest, indent=2))

    (root / "splits").mkdir(exist_ok=True)
    (root / "results").mkdir(exist_ok=True)

    cfg = {
        "cohort": "synth",
        "archive_url": "synthetic://fixture",
        "files": {"clinical_patient": "data_clinical_patient.txt",
                  "clinical_sample": "data_clinical_sample.txt",
                  "expression": "data_mrna_seq_v2_rsem.txt",
                  "expression_fallback": "data_mrna_seq_v2_rsem.txt",
                  "mutations": "data_mutations.txt"},
        "columns": {"patient_id": "PATIENT_ID", "sample_id": "SAMPLE_ID",
                    "os_months": "OS_MONTHS", "os_status": "OS_STATUS",
                    "sample_patient_id": "PATIENT_ID"},
        "os_status_map": {"deceased": "1:DECEASED", "living": "0:LIVING"},
        "covariates": {"age": "AGE", "sex": "SEX", "stage": "AJCC_PATHOLOGIC_TUMOR_STAGE"},
        "stage_map": {"STAGE I": "I", "STAGE II": "II", "STAGE IIIA": "III", "STAGE IV": "IV"},
        "sample_type_suffix": "-01",
        "n_expression_genes": 50,
        "mutation_genes": ["TP53", "KRAS"],
    }
    (root / "cohorts" / "synth.yaml").write_text(yaml.safe_dump(cfg))
    return root


@pytest.fixture()
def synth_root(tmp_path):
    return _make_cohort_dir(tmp_path)


@pytest.fixture()
def synth_split(synth_root):
    from oncocs.cli import main
    main(["--data-dir", str(synth_root), "split", "--cohort", "synth", "--seed", "20240601"])
    return synth_root
