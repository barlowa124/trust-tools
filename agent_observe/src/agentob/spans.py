"""Span model and trace ingestion.

Internal span shape: a plain dict with span_id, parent_id, name, kind,
start_ms, end_ms, attrs. `kind` is one of: agent, step, llm, tool_call,
tool_result, other. Tool-call spans carry attrs["tool"] and
attrs["args"]; llm/assistant spans carry attrs["text"].

Two input forms are accepted: the flat schema below, or a minimal OTLP
JSON export (see otlp.py — common fields only, not the full spec).
"""

from __future__ import annotations

import json
from pathlib import Path

KINDS = {"agent", "step", "llm", "tool_call", "tool_result", "other"}


class TraceError(ValueError):
    pass


def _validate(spans: list[dict]) -> list[dict]:
    ids, out = set(), []
    for i, s in enumerate(spans):
        sid = s.get("span_id")
        if not sid:
            raise TraceError(f"span[{i}] missing span_id")
        if sid in ids:
            raise TraceError(f"duplicate span_id {sid}")
        ids.add(sid)
        kind = s.get("kind", "other")
        if kind not in KINDS:
            raise TraceError(f"span[{i}] bad kind {kind!r}")
        start = float(s.get("start_ms", 0) or 0)
        end = float(s.get("end_ms", start) or start)
        if end < start:
            raise TraceError(f"span[{i}] end before start")
        out.append({
            "span_id": sid,
            "parent_id": s.get("parent_id"),
            "name": s.get("name", sid),
            "kind": kind,
            "start_ms": start,
            "end_ms": end,
            "attrs": dict(s.get("attrs") or {}),
        })
    for s in out:
        if s["parent_id"] and s["parent_id"] not in ids:
            raise TraceError(
                f"span {s['span_id']} has unknown parent "
                f"{s['parent_id']}")
    return out


def load(path: str | Path) -> list[dict]:
    """Load a trace file: flat span list or OTLP-lite export."""
    doc = json.loads(Path(path).read_text())
    spans = doc["spans"] if isinstance(doc, dict) and "spans" in doc else doc
    if isinstance(doc, dict) and "resourceSpans" in doc:
        from . import otlp
        spans = otlp.to_spans(doc)
    if not isinstance(spans, list):
        raise TraceError("trace must be a span list or OTLP export")
    return _validate(spans)


def children(spans: list[dict], span_id: str | None) -> list[dict]:
    """Direct children of a span (roots when span_id is None),
    ordered by start time."""
    return sorted(
        (s for s in spans if s["parent_id"] == span_id),
        key=lambda s: s["start_ms"])


def duration_ms(span: dict) -> float:
    return span["end_ms"] - span["start_ms"]


def tool_spans(spans: list[dict]) -> list[dict]:
    """Spans carrying a tool call, ordered by start."""
    return sorted((s for s in spans if s["kind"] == "tool_call"),
                  key=lambda s: s["start_ms"])
