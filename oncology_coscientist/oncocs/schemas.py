"""Pandera schemas for raw and harmonized cohort frames.

Loaders validate against these schemas; a malformed frame raises
pandera.errors.SchemaError instead of being silently coerced.
"""
from __future__ import annotations

import pandas as pd
import pandera.pandas as pa

from oncocs.config import CohortConfig


def clinical_patient_schema(cfg: CohortConfig) -> pa.DataFrameSchema:
    """One row per patient; configured clinical columns present; patient id unique.

    Raw cBioPortal frames are read as strings and may contain missing
    values; missingness filtering happens in harmonize(), not here.
    """
    cols = {
        cfg.patient_id: pa.Column(str, unique=True, nullable=True),
        cfg.os_months: pa.Column(str, nullable=True),
        cfg.os_status: pa.Column(str, nullable=True),
    }
    for raw_col in cfg.covariates.values():
        if raw_col:
            cols[raw_col] = pa.Column(str, nullable=True)
    return pa.DataFrameSchema(cols, strict=False)


def clinical_sample_schema(cfg: CohortConfig) -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {cfg.columns["sample_id"]: pa.Column(str, nullable=True),
         cfg.columns["sample_patient_id"]: pa.Column(str, nullable=True)},
        strict=False)


def mutations_schema(cfg: CohortConfig) -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {"Hugo_Symbol": pa.Column(str, nullable=False),
         "Tumor_Sample_Barcode": pa.Column(str, nullable=False)},
        strict=False)


def expression_schema(cfg: CohortConfig) -> pa.DataFrameSchema:
    """genes x samples frame: gene-id column present, every sample value numeric."""
    def _numeric(df: pd.DataFrame) -> bool:
        idcol = "Hugo_Symbol" if "Hugo_Symbol" in df.columns else df.columns[0]
        if not isinstance(df[idcol], pd.Series):
            return False  # duplicated gene-id column name
        vals = df.drop(columns=[idcol, "Entrez_Gene_Id"], errors="ignore")
        return bool(pd.to_numeric(vals.stack(), errors="coerce").notna().all())

    return pa.DataFrameSchema(
        checks=[pa.Check(_numeric, error="expression frame contains non-numeric values")],
        strict=False)


def survival_schema(cfg: CohortConfig) -> pa.DataFrameSchema:
    """Harmonized patient table: one row per patient, positive os_months, event in {0,1}."""
    pid = cfg.patient_id
    mut_cols = {f"mut_{g}": pa.Column(float, nullable=True,
                                    checks=pa.Check.isin([0.0, 1.0]))
                for g in cfg.mutation_genes}
    return pa.DataFrameSchema(
        {
            pid: pa.Column(str, unique=True),
            "sample_id": pa.Column(str),
            "os_months": pa.Column(float, checks=pa.Check.gt(0)),
            "event": pa.Column(float, checks=pa.Check.isin([0.0, 1.0])),
            **mut_cols,
        },
        strict=False,
    )


def validate_survival_frame(patients: pd.DataFrame, cfg: CohortConfig) -> None:
    """Validate the harmonized patients frame (index = patient id)."""
    df = patients.reset_index()
    schema = survival_schema(cfg)
    missing_required = [c for c in (cfg.patient_id, "sample_id", "os_months", "event")
                        if c not in df.columns]
    if missing_required:
        raise pa.errors.SchemaError(
            schema, df, f"survival frame missing required columns {missing_required}")
    # optional mut_* columns are only checked when present
    schema.columns = {k: v for k, v in schema.columns.items() if k in df.columns}
    schema.validate(df)
