"""Evidence record per run + verification."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import uuid
from datetime import UTC, datetime
from importlib.metadata import version as pkg_version
from pathlib import Path

TRACKED_PACKAGES = ["lifelines", "scikit-survival", "numpy", "pandas", "scikit-learn"]


def _git_commit(root: Path) -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


def _git_dirty(root: Path) -> bool | None:
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                             capture_output=True, text=True, check=True).stdout.strip()
        return bool(out)
    except Exception:
        return None


def build_record(cohort: str, seed: int, root: Path, data_manifest_sha256: str,
                 split_sha256: str, config_sha256: str) -> dict:
    return {
        "run_id": uuid.uuid4().hex[:12],
        "timestamp": datetime.now(UTC).isoformat(),
        "cohort": cohort,
        "git_commit": _git_commit(root),
        "git_dirty": _git_dirty(root),
        "python_version": platform.python_version(),
        "package_versions": {p: pkg_version(p) for p in TRACKED_PACKAGES},
        "data_manifest_sha256": data_manifest_sha256,
        "split_sha256": split_sha256,
        "seed": seed,
        "config_sha256": config_sha256,
        "checks": [],
        "models": {},
        "missingness": {},
        "dropped": {},
    }


def results_dir(root: Path, cohort: str, run_id: str) -> Path:
    return Path(root) / "results" / cohort / run_id


def write_results(record: dict, root: Path) -> Path:
    d = results_dir(Path(root), record["cohort"], record["run_id"])
    d.mkdir(parents=True, exist_ok=True)
    path = d / "results.json"
    path.write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def strip_volatile(record: dict) -> dict:
    """Copy of a results record minus fields that legitimately differ across runs."""
    r = json.loads(json.dumps(record))
    for k in ("run_id", "timestamp", "git_commit", "git_dirty"):
        r.pop(k, None)
    return r


def canonical_sha(record: dict) -> str:
    return hashlib.sha256(
        json.dumps(strip_volatile(record), sort_keys=True, default=str).encode()
    ).hexdigest()
