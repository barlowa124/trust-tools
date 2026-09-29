"""Shadow evaluation: grade primary-vs-candidate divergence on a served
traffic slice.

modelserve records the shadow output beside each sampled response, but
agreement alone is not a deployment decision — "they differed" needs
"and which one was right". Given a serve log plus the evalh task spec the
prompts came from, this grades both sides of every shadowed response and
reports the cases where the candidate's output changed the grade.

Reads JSONL files as data; nothing here imports modelserve — the record
shape is the contract.
"""

from __future__ import annotations

import json
from collections import Counter

from .graders import grade, is_degenerate


def _label(out: str, grader: dict) -> tuple[str, float]:
    g = grade(out, grader)
    if g["label"] not in ("abstains",) and is_degenerate(out):
        return "degenerate", 0.0
    return g["label"], g["score"]


def grade_shadow(serve_log: str, tasks: list[dict]) -> dict:
    """Grade every shadowed serve_response against its task's grader.

    Returns a comparison report: counts by (primary, shadow) label pair,
    per-case detail, and headline counters a deploy gate would read.
    """
    by_prompt = {t["prompt"]: t for t in tasks}
    records = [json.loads(l) for l in open(serve_log) if l.strip()]
    cases, pairs = [], Counter()
    n_shadow = 0
    for r in records:
        sh = r.get("shadow")
        if not sh:
            continue
        n_shadow += 1
        task = by_prompt.get(r["input"]["text"])
        grader = task["grader"] if task else {"kind": "exact",
                                             "value": ""}
        pl, ps = _label(r["output"]["text"], grader)
        sl, ss = _label(sh["output"], grader)
        pair = (pl, sl)
        pairs[pair] += 1
        cases.append({
            "input_sha256": r["input"]["sha256"],
            "task_id": task["id"] if task else None,
            "primary": {"label": pl, "score": ps},
            "shadow": {"label": sl, "score": ss},
            "same_label": pl == sl,
            "grade_change": ps != ss,
        })
    n_change = sum(1 for c in cases if c["grade_change"])
    return {
        "n_requests": len(records),
        "n_shadowed": n_shadow,
        "n_grade_changes": n_change,
        "label_pairs": {f"{a}|{b}": n for (a, b), n in
                        sorted(pairs.items())},
        "cases": cases,
    }


def shadow_table(rep: dict) -> str:
    lines = [
        f"| shadowed | grade changes |",
        f"|---|---|",
        f"| {rep['n_shadowed']} | {rep['n_grade_changes']} |",
        "",
        "| primary | shadow | n |", "|---|---|---|"]
    for pair, n in rep["label_pairs"].items():
        a, b = pair.split("|")
        lines.append(f"| {a} | {b} | {n} |")
    return "\n".join(lines)
