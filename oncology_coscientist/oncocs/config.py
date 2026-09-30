"""Cohort configuration loading."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CohortConfig:
    cohort: str
    archive_url: str
    file_base_url: str
    file_base_url_alt: str
    files: dict
    columns: dict
    os_status_map: dict
    covariates: dict
    stage_map: dict
    sample_type_suffix: str
    n_expression_genes: int
    max_missing_fraction: float = 0.20
    mutation_genes: list = field(default_factory=list)
    entrez_ids: dict = field(default_factory=dict)
    excluded_genes: list = field(default_factory=list)
    excluded_gene_patterns: list = field(default_factory=list)
    rag_query: str = ""
    rag_docs: list = field(default_factory=list)
    rag_mode: str = "bm25"
    config_sha256: str = ""

    @property
    def patient_id(self) -> str:
        return self.columns["patient_id"]

    @property
    def os_months(self) -> str:
        return self.columns["os_months"]

    @property
    def os_status(self) -> str:
        return self.columns["os_status"]


def _sha256_of_obj(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


# Cohort-yaml keys that affect only the agent/RAG reporting layer, not the
# deterministic analysis. They are excluded from config_sha256 so prompt-side
# edits do not invalidate computed results.
AGENT_ONLY_KEYS = ("rag_query", "rag_docs", "rag_mode")


def load_cohort(name: str, root: Path | str = DEFAULT_ROOT) -> CohortConfig:
    path = Path(root) / "cohorts" / f"{name}.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg = CohortConfig(
        cohort=raw["cohort"],
        archive_url=raw.get("archive_url", ""),
        file_base_url=raw.get("file_base_url", ""),
        file_base_url_alt=raw.get("file_base_url_alt", ""),
        files=raw["files"],
        columns=raw["columns"],
        os_status_map=raw.get("os_status_map", {}),
        covariates=raw.get("covariates", {}),
        stage_map=raw.get("stage_map", {}),
        sample_type_suffix=raw.get("sample_type_suffix", "-01"),
        n_expression_genes=int(raw.get("n_expression_genes", 50)),
        max_missing_fraction=float(raw.get("max_missing_fraction", 0.20)),
        mutation_genes=list(raw.get("mutation_genes", [])),
        entrez_ids={k: int(v) for k, v in raw.get("entrez_ids", {}).items()},
        excluded_genes=list(raw.get("excluded_genes", [])),
        excluded_gene_patterns=list(raw.get("excluded_gene_patterns", [])),
        rag_query=raw.get("rag_query", ""),
        rag_docs=list(raw.get("rag_docs", [])),
        rag_mode=raw.get("rag_mode", "bm25"),
    )
    cfg.config_sha256 = _sha256_of_obj(
        {k: v for k, v in raw.items() if k not in AGENT_ONLY_KEYS})
    return cfg
