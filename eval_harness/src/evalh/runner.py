"""Eval runner: tasks -> model outputs -> grades -> hash-chained records.

`generate_fn` is injectable so the harness core is dependency-free and
testable offline; the HF backend lives in `hf.py`. Each result record
binds the task id, the output text hash, the grade, and the previous
record's id — a run cannot be reordered, edited, or truncated without the
chain check failing. Prompts are hashed, not copied, into records; the
task spec is the committed artifact and the run log references it by hash.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Callable

from .chainfmt import canonical_json, sha256_bytes, sha256_text
from .graders import grade, is_degenerate

SCHEMA_VERSION = 1


def run(tasks: list[dict], generate_fn: Callable[[str], str],
        model: dict, *, spec_sha: str | None = None,
        generation: dict | None = None) -> tuple[list[dict], dict]:
    """Run every task through generate_fn; return (records, summary)."""
    if spec_sha is None:
        spec_sha = sha256_bytes(canonical_json(tasks))
    records: list[dict] = []
    prev_id = "genesis"
    for i, t in enumerate(tasks):
        t0 = time.perf_counter()
        out = generate_fn(t["prompt"])
        dt = time.perf_counter() - t0
        g = grade(out, t["grader"])
        label = g["label"]
        score = g["score"]
        if label not in ("abstains",) and is_degenerate(out):
            # Degenerate output cannot earn credit: an infinite loop that
            # incidentally contains the gold token is not an answer.
            label, score = "degenerate", 0.0
        body = {
            "v": SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "kind": "eval_result",
            "model": model,
            "spec_sha256": spec_sha,
            "generation": generation or {},
            "task_id": t["id"],
            "tag": t["tag"],
            "output": {"text": out, "sha256": sha256_text(out)},
            "grade": {"label": label, "score": score,
                      "grader": t["grader"]},
            "gen_time_s": round(dt, 4),
            "chain_prev": prev_id,
        }
        body["result_id"] = "evr-" + sha256_bytes(canonical_json(body))[:16]
        records.append(body)
        prev_id = body["result_id"]

    return records, summarize(tasks, records, model, spec_sha)


def summarize(tasks: list[dict], records: list[dict], model: dict,
              spec_sha: str) -> dict:
    """Aggregate a run: overall score plus per-tag label counts."""
    tags: dict[str, list[dict]] = {}
    for r in records:
        tags.setdefault(r["tag"], []).append(r)
    per_tag = {}
    for tag, rs in sorted(tags.items()):
        from collections import Counter
        labels = Counter(r["grade"]["label"] for r in rs)
        per_tag[tag] = {
            "n": len(rs),
            "score": sum(r["grade"]["score"] for r in rs) / len(rs),
            "labels": dict(labels),
        }
    n = len(records)
    return {
        "v": SCHEMA_VERSION,
        "model": model,
        "spec_sha256": spec_sha,
        "n_tasks": n,
        "score": sum(r["grade"]["score"] for r in records) / max(n, 1),
        "per_tag": per_tag,
        "first_result": records[0]["result_id"] if records else None,
        "last_result": records[-1]["result_id"] if records else None,
    }


def record_hash(record: dict) -> str:
    body = {k: v for k, v in record.items() if k != "result_id"}
    return "evr-" + sha256_bytes(canonical_json(body))[:16]


def check_log(records: list[dict]) -> list[str]:
    problems = []
    prev_id = "genesis"
    spec = None
    model_sha = None
    for i, r in enumerate(records):
        rid = r.get("result_id", "?")
        if record_hash(r) != rid:
            problems.append(f"[{i}] {rid}: content hash mismatch "
                            "(body tampered)")
        if r.get("chain_prev") != prev_id:
            problems.append(f"[{i}] {rid}: chain break")
        if r.get("output", {}).get("sha256") != sha256_text(
                r.get("output", {}).get("text", "")):
            problems.append(f"[{i}] {rid}: output hash mismatch")
        if spec is None:
            spec = r.get("spec_sha256")
            model_sha = sha256_bytes(canonical_json(r.get("model")))
        else:
            if r.get("spec_sha256") != spec:
                problems.append(f"[{i}] {rid}: spec changed mid-log")
            if sha256_bytes(canonical_json(r.get("model"))) != model_sha:
                problems.append(f"[{i}] {rid}: model changed mid-log")
        prev_id = rid
    return problems


def load_log(path: str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
