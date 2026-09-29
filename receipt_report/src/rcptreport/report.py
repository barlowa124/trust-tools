"""Report generator: receipt logs -> markdown audit document.

One section per input log, headed by the record kind detected. Every
number in the rendered document is recomputed from the records at build
time, and chain integrity is checked first — a broken chain lands in the
report as a finding, not a silent omission.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def load_log(path: str) -> list[dict]:
    return [json.loads(l) for l in open(path, encoding="utf-8")
            if l.strip()]


def detect_kind(records: list[dict]) -> str:
    kinds = {r.get("kind") for r in records}
    if len(kinds) != 1:
        return "mixed"
    return kinds.pop() or "unknown"


# -- chain verification, one per record family ---------------------------

def _check_eval(records):
    problems, prev = [], "genesis"
    for i, r in enumerate(records):
        body = {k: v for k, v in r.items() if k != "result_id"}
        if "evr-" + sha256_bytes(canonical_json(body))[:16] \
                != r.get("result_id"):
            problems.append(f"[{i}] eval record hash mismatch")
        if r.get("chain_prev") != prev:
            problems.append(f"[{i}] eval chain break")
        prev = r.get("result_id")
    return problems


def _check_serve(records):
    problems, prev = [], "genesis"
    for i, r in enumerate(records):
        body = {k: v for k, v in r.items() if k != "response_id"}
        if "srv-" + sha256_bytes(canonical_json(body))[:16] \
                != r.get("response_id"):
            problems.append(f"[{i}] serve record hash mismatch")
        if r.get("chain_prev") != prev:
            problems.append(f"[{i}] serve chain break")
        prev = r.get("response_id")
    return problems


def _check_receipt(records):
    problems, prev = [], "genesis"
    for i, r in enumerate(records):
        body = {k: v for k, v in r.items() if k != "receipt_id"}
        if "rcpt-" + sha256_bytes(canonical_json(body))[:16] \
                != r.get("receipt_id"):
            problems.append(f"[{i}] receipt hash mismatch")
        prev_r = r.get("prev_receipt_id", r.get("chain_prev"))
        if prev_r != prev:
            problems.append(f"[{i}] receipt chain break")
        prev = r.get("receipt_id")
    return problems


_CHECKERS = {"eval_result": _check_eval, "serve_response": _check_serve}


def check_chain(records: list[dict]) -> list[str]:
    kind = detect_kind(records)
    if kind in _CHECKERS:
        return _CHECKERS[kind](records)
    if kind == "mixed":
        return ["mixed record kinds — cannot verify as one chain"]
    # llmreceipt records have no "kind"; identify by receipt_id field
    if records and "receipt_id" in records[0]:
        return _check_receipt(records)
    return ["unrecognized record kind"]


# -- section renderers ---------------------------------------------------

def _model_line(r: dict) -> str:
    m = r.get("model", {})
    name = m.get("name") or m.get("generate_fn") or "unknown"
    w = m.get("weights_sha256", {})
    wtxt = ", ".join(f"{k}={v[:12]}…" for k, v in w.items()) or "n/a"
    return f"**Model**: `{name}` — weights {wtxt}"


def _eval_section(records, label):
    labels = Counter(r["grade"]["label"] for r in records)
    tags = sorted({r["tag"] for r in records})
    per_tag = {}
    for t in tags:
        rs = [r for r in records if r["tag"] == t]
        per_tag[t] = (sum(r["grade"]["score"] for r in rs) / len(rs),
                      Counter(r["grade"]["label"] for r in rs))
    lines = [f"## Evaluation run — {label}", "",
             _model_line(records[0]),
             f"**Spec**: sha256 `{records[0].get('spec_sha256', '?')[:16]}…`",
             f"**Tasks**: {len(records)} across tags: {', '.join(tags)}",
             "",
             "| tag | score | labels |", "|---|---|---|"]
    for t in tags:
        sc, c = per_tag[t]
        lines.append(f"| {t} | {sc:.2f} | "
                     + " ".join(f"{k}:{v}" for k, v in sorted(c.items()))
                     + " |")
    lines += ["", f"Overall label counts: "
              + ", ".join(f"{k}={v}" for k, v in sorted(labels.items()))]
    return lines


def _serve_section(records, label):
    lat = [r.get("latency_s", 0) for r in records]
    n_shadow = sum(1 for r in records if r.get("shadow"))
    div = sum(1 for r in records
              if r.get("shadow") and not r["shadow"]["agrees_with_primary"])
    lines = [f"## Serving log — {label}", "",
             _model_line(records[0]),
             f"**Responses**: {len(records)}",
             f"**Latency**: mean {sum(lat)/len(lat):.4f}s, "
             f"max {max(lat):.4f}s",
             f"**Shadow comparisons**: {n_shadow}"
             + (f" ({div} diverged)" if n_shadow else "")]
    return lines


def _receipt_section(records, label):
    lines = [f"## Inference receipts — {label}", "",
             f"**Calls**: {len(records)}",
             f"**First**: `{records[0]['receipt_id'][:20]}…`",
             f"**Last**: `{records[-1]['receipt_id'][:20]}…`"]
    return lines


_RENDERERS = {"eval_result": _eval_section,
              "serve_response": _serve_section}


def render(log_paths: list[str], title: str = "Audit report") -> str:
    """Build a markdown report over one or more JSONL receipt logs."""
    lines = [f"# {title}", "",
             f"Generated {datetime.now(timezone.utc).isoformat()} "
             "from hash-chained records. Every figure below is recomputed "
             "from the committed logs; chain integrity was checked per log "
             "at build time.", ""]
    all_ok = True
    for path in log_paths:
        records = load_log(path)
        if not records:
            lines += [f"## {path}", "", "*empty log*", ""]
            continue
        problems = check_chain(records)
        name = path.rsplit("/", 1)[-1]
        if problems:
            all_ok = False
            lines += [f"## {name}", "",
                      f"**CHAIN INTEGRITY: {len(problems)} problems**", ""]
            lines += [f"- {p}" for p in problems[:20]]
            lines.append("")
            continue
        kind = detect_kind(records)
        if kind == "unknown" and "receipt_id" in records[0]:
            kind = "receipt"
        lines += [f"*chain verified: {len(records)} records, "
                  f"kind={detect_kind(records)}*", ""]
        renderer = (_RENDERERS.get(detect_kind(records))
                    or (_receipt_section if "receipt_id" in records[0]
                        else None))
        if renderer:
            lines += renderer(records, name) + [""]
        else:
            lines += [f"## {name}", "",
                      f"{len(records)} records of unrecognized kind.", ""]

    lines += ["## Integrity summary", "",
              "All chains verified." if all_ok else
              "**One or more logs failed chain verification — see above.**",
              "",
              "## Limits", "",
              "- This report covers only the recorded runs; it is not a "
              "capability or safety claim about the model family.",
              "- Chain verification proves the logs are unmodified since "
              "creation, not that the underlying evaluations were correct.",
              "- Replay (re-running generation to compare outputs) is a "
              "stronger check and is reported separately where available."]
    return "\n".join(lines) + "\n"
