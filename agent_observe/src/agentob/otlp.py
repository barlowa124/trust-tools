"""Minimal OTLP/JSON trace mapper.

Covers the common export shape: resourceSpans[].scopeSpans[].spans[]
with name, spanId, parentSpanId, startTimeUnixNano, endTimeUnixNano and
an attributes list. This is deliberately not the full OTLP spec — no
protobuf ingest, no events/links, no resource attribute merging. Fields
not mapped are dropped rather than guessed.
"""

from __future__ import annotations

_NS_PER_MS = 1_000_000


def _attr_list(attrs: list[dict]) -> dict:
    out = {}
    for a in attrs or []:
        v = a.get("value", {})
        for k in ("stringValue", "intValue", "doubleValue",
                  "boolValue"):
            if k in v:
                out[a["key"]] = v[k]
                break
    return out


def _kind(attrs: dict, name: str) -> str:
    k = attrs.get("agentob.kind") or attrs.get("gen_ai.operation.name")
    if k in ("agent", "step", "llm", "tool_call", "tool_result"):
        return k
    tool = attrs.get("gen_ai.tool.name") or attrs.get("tool")
    if tool:
        return "tool_call"
    if "gen_ai.completion" in attrs or "gen_ai.prompt" in attrs:
        return "llm"
    return "other"


def to_spans(export: dict) -> list[dict]:
    spans = []
    for rs in export.get("resourceSpans", []):
        for ss in rs.get("scopeSpans", []):
            for s in ss.get("spans", []):
                attrs = _attr_list(s.get("attributes"))
                kind = _kind(attrs, s.get("name", ""))
                out = {
                    "span_id": s.get("spanId"),
                    "parent_id": s.get("parentSpanId") or None,
                    "name": s.get("name", s.get("spanId", "")),
                    "kind": kind,
                    "start_ms": float(s.get("startTimeUnixNano", 0))
                                / _NS_PER_MS,
                    "end_ms": float(s.get("endTimeUnixNano", 0))
                              / _NS_PER_MS,
                    "attrs": {},
                }
                if kind == "tool_call":
                    out["attrs"]["tool"] = (
                        attrs.get("gen_ai.tool.name")
                        or attrs.get("tool"))
                    out["attrs"]["args"] = attrs.get(
                        "gen_ai.tool.call.arguments") or \
                        attrs.get("args") or {}
                elif kind == "llm":
                    out["attrs"]["text"] = (
                        attrs.get("gen_ai.completion")
                        or attrs.get("text") or "")
                spans.append(out)
    return spans
