"""Normalized trajectory event model.

A trajectory is a list of events in session order. Events are the common
denominator between agent transcript formats (Devin CLI sqlite, ACP logs,
hand-written fixtures). Analysis and reporting work only on this schema.

Event kinds:
  user         user message; text field
  assistant    assistant message text (stated claims live here)
  thinking     assistant reasoning; optional, dropped by sanitize
  plan         plan snapshot; plan field is [{content, status}]
  tool_call    tool invocation; tool + arg fields
  tool_result  tool outcome; call_id links to the tool_call
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator

SCHEMA_VERSION = 1

KINDS = {"user", "assistant", "thinking", "plan", "tool_call", "tool_result"}


@dataclass
class Event:
    i: int                       # position in the trajectory
    kind: str                    # one of KINDS
    session: str = ""
    t: int | None = None         # epoch seconds when known
    text: str = ""               # message text or result body
    tool: str = ""               # tool_call: tool name
    call_id: str = ""            # tool_call/tool_result link id
    plan: list[dict] = field(default_factory=list)   # plan: item snapshots
    args: dict = field(default_factory=dict)          # tool_call: select args

    def to_dict(self) -> dict:
        d = asdict(self)
        d["v"] = SCHEMA_VERSION
        return {k: v for k, v in d.items() if v not in ("", None, []) or k in ("i", "kind", "v")}

    @staticmethod
    def from_dict(d: dict) -> "Event":
        return Event(
            i=int(d["i"]), kind=d["kind"], session=d.get("session", ""),
            t=d.get("t"), text=d.get("text", ""), tool=d.get("tool", ""),
            call_id=d.get("call_id", ""), plan=d.get("plan", []),
            args=d.get("args", {}),
        )


def write_jsonl(events: list[Event], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")


def read_jsonl(path: str) -> list[Event]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(Event.from_dict(json.loads(line)))
    return out


def iter_jsonl(path: str) -> Iterator[Event]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield Event.from_dict(json.loads(line))
