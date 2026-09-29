"""Trajaudit-compatible event export for monitored sessions.

`EventRecorder` wraps a Monitor: every gated call appends a `tool_call`
event plus a `tool_result` event carrying the verdict, in the same
schema trajaudit parses. A monitored session can then be audited with
the full post-hoc detector suite — gate decisions and forensic findings
over one event stream.

The module stays stdlib-only: `Event` objects are plain dicts matching
trajaudit's serialized form (`model.Event.to_dict`), so no import of the
sibling package is required. The monorepo interop test verifies the
emitted stream parses under trajaudit itself.
"""

from __future__ import annotations

import json

SCHEMA_VERSION = 1


class EventRecorder:
    """Wraps a Monitor; records gated calls as trajaudit-schema events."""

    def __init__(self, monitor, *, session: str = "monitored"):
        self.monitor = monitor
        self.session = session
        self.events: list[dict] = []

    def gate(self, tool: str, args) -> object:
        """Gate a call through the wrapped monitor; record both the call
        and the verdict as events. DenyError propagates after recording —
        the denied call stays in the event stream."""
        i = len(self.events)
        self.events.append({
            "v": SCHEMA_VERSION, "i": i, "kind": "tool_call",
            "session": self.session, "tool": tool,
            "call_id": f"mc{i}",
            "args": args if isinstance(args, dict) else {"args": str(args)},
        })
        try:
            v = self.monitor.gate(tool, args)
            action, reason = v.action, v.reason
        except Exception as e:
            # DenyError (or a monitor bug): the verdict still lands in the
            # stream so post-hoc audit sees the attempt.
            verdict = getattr(e, "verdict", None)
            action = getattr(verdict, "action", "error")
            reason = getattr(verdict, "reason", str(e))
            self.events.append({
                "v": SCHEMA_VERSION, "i": i + 1, "kind": "tool_result",
                "session": self.session, "call_id": f"mc{i}",
                "text": f"monitor: {action} ({reason})",
            })
            raise
        self.events.append({
            "v": SCHEMA_VERSION, "i": i + 1, "kind": "tool_result",
            "session": self.session, "call_id": f"mc{i}",
            "text": f"monitor: {action} ({reason})",
        })
        return v

    def write_jsonl(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for e in self.events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
