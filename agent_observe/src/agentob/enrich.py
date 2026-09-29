"""Enrich a span list with monitor verdicts and audit findings.

gate_spans runs every tool_call span through agentmon.policy.evaluate —
non-raising, so the verdict lands on the span even when it would deny.
to_events converts the ordered span list into trajaudit-schema event
dicts; audit runs the detector suite over them when trajaudit is
importable.

Sibling packages are soft dependencies: agentob still ingests and
renders without them, and the report says what was skipped.
"""

from __future__ import annotations

from . import spans as _spans


def gate_spans(spans: list[dict], policy: dict, cwd: str = ".",
               monitor=None) -> list[dict]:
    """Attach `verdict` to each tool_call span. When `monitor` is given
    (an agentmon.Monitor), flagged/denied verdicts are also written to
    its hash-chained record log via _record."""
    from agentmon.policy import evaluate
    verdicts = []
    for s in _spans.tool_spans(spans):
        v = evaluate(policy, s["attrs"].get("tool", ""),
                     s["attrs"].get("args"), cwd=cwd)
        s["verdict"] = {"action": v.action, "rule": v.rule,
                        "severity": v.severity, "reason": v.reason}
        verdicts.append(s["verdict"])
        if monitor is not None and v.action in ("flag", "deny"):
            monitor._record(s["attrs"].get("tool", ""),
                            s["attrs"].get("args"), v)
    return verdicts


def to_events(spans: list[dict], session: str = "trace") -> list[dict]:
    """Ordered spans -> trajaudit-schema event dicts."""
    events = []
    call_seq = {}
    for s in sorted(spans, key=lambda s: (s["start_ms"], s["span_id"])):
        i = len(events)
        if s["kind"] == "tool_call":
            cid = s["span_id"]
            call_seq[cid] = i
            events.append({
                "v": 1, "i": i, "kind": "tool_call", "session": session,
                "t": s["start_ms"] / 1000 if s["start_ms"] else None,
                "tool": s["attrs"].get("tool", s["name"]),
                "call_id": cid,
                "args": s["attrs"].get("args")
                if isinstance(s["attrs"].get("args"), dict)
                else {"args": str(s["attrs"].get("args", ""))},
            })
        elif s["kind"] == "tool_result":
            events.append({
                "v": 1, "i": i, "kind": "tool_result", "session": session,
                "call_id": s["parent_id"] or s["span_id"],
                "text": str(s["attrs"].get("text", s["name"])),
            })
        elif s["kind"] in ("llm", "agent"):
            text = str(s["attrs"].get("text", ""))
            if text:
                events.append({
                    "v": 1, "i": i, "kind": "assistant",
                    "session": session, "text": text,
                })
    return events


def audit(events: list[dict]) -> list[dict] | None:
    """Run trajaudit detectors over converted events. Returns None when
    trajaudit is not importable — the caller reports the skip."""
    try:
        from trajaudit.detectors import analyze
        from trajaudit.model import Event
    except ImportError:
        return None
    evs = [Event.from_dict(e) for e in events]
    return analyze(evs)
