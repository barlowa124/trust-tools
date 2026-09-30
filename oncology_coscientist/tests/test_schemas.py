"""Schema validation tests: malformed frames raise SchemaError, valid ones pass."""
from __future__ import annotations

import pandas as pd
import pandera.errors
import pytest

from oncocs import schemas
from oncocs.config import load_cohort


@pytest.fixture()
def cfg(synth_root):
    return load_cohort("synth", synth_root)


def test_clinical_patient_passes(cfg, synth_root):
    df = pd.read_csv(synth_root / "data" / "synth" / "raw" / "data_clinical_patient.txt",
                     sep="\t", comment="#", dtype=str)
    schemas.clinical_patient_schema(cfg).validate(df)


def test_clinical_patient_missing_column(cfg):
    df = pd.DataFrame({"PATIENT_ID": ["P1"], "OS_STATUS": ["1:DECEASED"]})
    with pytest.raises(pandera.errors.SchemaError):
        schemas.clinical_patient_schema(cfg).validate(df)


def test_clinical_patient_duplicate_id(cfg):
    df = pd.DataFrame({"PATIENT_ID": ["P1", "P1"], "OS_MONTHS": ["10", "20"],
                       "OS_STATUS": ["1:DECEASED", "0:LIVING"],
                       "AGE": ["60", "70"], "SEX": ["Male", "Female"],
                       "AJCC_PATHOLOGIC_TUMOR_STAGE": ["STAGE I", "STAGE II"]})
    with pytest.raises(pandera.errors.SchemaError):
        schemas.clinical_patient_schema(cfg).validate(df)


def test_clinical_sample_missing_column(cfg):
    df = pd.DataFrame({"SAMPLE_ID": ["S1"]})
    with pytest.raises(pandera.errors.SchemaError):
        schemas.clinical_sample_schema(cfg).validate(df)


def test_mutations_missing_column(cfg):
    df = pd.DataFrame({"Hugo_Symbol": ["TP53"]})
    with pytest.raises(pandera.errors.SchemaError):
        schemas.mutations_schema(cfg).validate(df)


def test_expression_wrong_dtype(cfg):
    df = pd.DataFrame({"Hugo_Symbol": ["TP53", "KRAS"],
                       "S1": ["not_a_number", "1.0"]})
    with pytest.raises(pandera.errors.SchemaError):
        schemas.expression_schema(cfg).validate(df)


def test_expression_passes(cfg):
    df = pd.DataFrame({"Hugo_Symbol": ["TP53", "KRAS"],
                       "S1": ["1.5", "2.0"], "S2": ["0.0", "3.3"]})
    schemas.expression_schema(cfg).validate(df)


def _patients(**overrides):
    df = pd.DataFrame({
        "PATIENT_ID": ["P1", "P2"],
        "sample_id": ["P1-01", "P2-01"],
        "os_months": [10.0, 20.0],
        "event": [1.0, 0.0],
        "mut_TP53": [1.0, 0.0],
        "mut_KRAS": [0.0, float("nan")],
    })
    for k, v in overrides.items():
        df[k] = v
    return df.set_index("PATIENT_ID")


def test_survival_passes(cfg):
    schemas.validate_survival_frame(_patients(), cfg)


def test_survival_negative_time(cfg):
    with pytest.raises(pandera.errors.SchemaError):
        schemas.validate_survival_frame(_patients(os_months=[10.0, -5.0]), cfg)


def test_survival_wrong_dtype(cfg):
    df = _patients()
    df["os_months"] = df["os_months"].astype(str)
    with pytest.raises(pandera.errors.SchemaError):
        schemas.validate_survival_frame(df, cfg)


def test_survival_duplicate_patient(cfg):
    df = _patients()
    df.index = pd.Index(["P1", "P1"], name="PATIENT_ID")
    with pytest.raises(pandera.errors.SchemaError):
        schemas.validate_survival_frame(df, cfg)


def test_survival_bad_event(cfg):
    with pytest.raises(pandera.errors.SchemaError):
        schemas.validate_survival_frame(_patients(event=[1.0, 3.0]), cfg)


def test_loaders_validate(synth_root, cfg):
    """End-to-end: loaders return schema-valid frames for the synth fixture."""
    from oncocs.data.load import (
        load_clinical_patient,
        load_clinical_sample,
        load_expression,
        load_mutations,
    )
    assert not load_clinical_patient(cfg, synth_root).empty
    assert not load_clinical_sample(cfg, synth_root).empty
    assert not load_expression(cfg, synth_root).empty
    assert not load_mutations(cfg, synth_root).empty


def test_config_hash_excludes_agent_keys(synth_root):
    """rag_query edits must not change config_sha256; covariates edits must."""
    import yaml

    from oncocs.config import AGENT_ONLY_KEYS, load_cohort

    assert "rag_query" in AGENT_ONLY_KEYS and "rag_docs" in AGENT_ONLY_KEYS
    ypath = synth_root / "cohorts" / "synth.yaml"
    raw = yaml.safe_load(ypath.read_text())
    raw["rag_query"] = "some query"
    raw["rag_docs"] = [{"doc_id": "d", "url": "https://x"}]
    ypath.write_text(yaml.safe_dump(raw))
    h1 = load_cohort("synth", synth_root).config_sha256
    raw["rag_query"] = "a completely different query"
    raw["rag_docs"] = [{"doc_id": "e", "url": "https://y"}, {"doc_id": "f"}]
    ypath.write_text(yaml.safe_dump(raw))
    assert load_cohort("synth", synth_root).config_sha256 == h1
    raw["covariates"]["stage"] = "AJCC_PATHOLOGIC_TUMOR_STAGE_V2"
    ypath.write_text(yaml.safe_dump(raw))
    assert load_cohort("synth", synth_root).config_sha256 != h1
