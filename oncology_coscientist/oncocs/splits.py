"""Frozen, hashed, stratified patient-level train/test splits."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from oncocs.config import DEFAULT_ROOT, CohortConfig


def split_sha256(train_ids: list, test_ids: list) -> str:
    canon = json.dumps({"train": sorted(train_ids), "test": sorted(test_ids)},
                       sort_keys=True).encode()
    return hashlib.sha256(canon).hexdigest()


def split_path(cfg: CohortConfig, root: Path | str = DEFAULT_ROOT) -> Path:
    return Path(root) / "splits" / f"{cfg.cohort}.json"


def make_split(patients: pd.DataFrame, cfg: CohortConfig, seed: int,
               test_fraction: float, data_manifest_sha256: str,
               root: Path | str = DEFAULT_ROOT, force: bool = False) -> dict:
    path = split_path(cfg, root)
    supersedes = None
    if path.exists():
        if not force:
            raise FileExistsError(f"Split file exists: {path}. Use --force to supersede.")
        supersedes = json.loads(path.read_text())["split_sha256"]

    ids = patients.index.to_numpy()
    events = patients["event"].to_numpy()
    train_ids, test_ids = train_test_split(
        ids, test_size=test_fraction, random_state=seed, stratify=events)

    split = {
        "cohort": cfg.cohort,
        "seed": seed,
        "test_fraction": test_fraction,
        "stratified_by": "event",
        "n_train": len(train_ids),
        "n_test": len(test_ids),
        "train_ids": sorted(train_ids.tolist()),
        "test_ids": sorted(test_ids.tolist()),
        "data_manifest_sha256": data_manifest_sha256,
    }
    split["split_sha256"] = split_sha256(split["train_ids"], split["test_ids"])
    if supersedes:
        split["supersedes"] = supersedes

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(split, indent=2) + "\n", encoding="utf-8")
    return split


def load_split(cfg: CohortConfig, root: Path | str = DEFAULT_ROOT) -> dict:
    return json.loads(split_path(cfg, root).read_text())
