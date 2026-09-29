"""Redaction pass for publishing trajectories.

Sanitizing is a transform on events, applied before committing an example.
It rewrites free-text fields (text, args values, plan content) in place.

What it covers:
  - absolute paths under $HOME          -> ~/
  - email addresses                     -> <email>
  - bearer/api-token-looking strings    -> <token>
  - IPv4 literals                       -> <ip>
  - thinking events                     -> dropped (reasoning may quote
    private context verbatim; keep it out of published artifacts)

It does not try to detect names or employer identifiers in prose; review
the sanitized output before publishing. The point is that redaction is a
pipeline step, not a promise.
"""

from __future__ import annotations

import os
import re

from .model import Event

_HOME = os.path.expanduser("~")

_RULES = [
    (re.compile(re.escape(_HOME) + r"[\w./~-]*"), lambda m: "~" + m.group(0)[len(_HOME):]),
    (re.compile(r"/Users/[^/\s'\"]+"), "~"),
    (re.compile(r"/home/[^/\s'\"]+"), "~"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<email>"),
    (re.compile(r"(?i)(bearer|api[_-]?key|token|secret|password)[=: ]\s*['\"]?[\w./~+-]{8,}"),
     r"\1=<token>"),
    (re.compile(r"\b(?!127\.|0\.0\.0\.0\b)(?:\d{1,3}\.){3}\d{1,3}\b"), "<ip>"),
]


def _clean(text: str) -> str:
    for pat, rep in _RULES:
        text = pat.sub(rep, text)
    return text


def sanitize(events: list[Event], drop_thinking: bool = True) -> list[Event]:
    out: list[Event] = []
    for ev in events:
        if drop_thinking and ev.kind == "thinking":
            continue
        ev = Event(**{f: getattr(ev, f) for f in
                      ("i", "kind", "session", "t", "text", "tool",
                       "call_id", "plan", "args")})
        ev.text = _clean(ev.text)
        ev.args = {k: _clean(v) if isinstance(v, str) else v
                   for k, v in ev.args.items()}
        ev.plan = [{**p, "content": _clean(p.get("content", ""))}
                   for p in ev.plan]
        out.append(ev)
    for i, ev in enumerate(out):
        ev.i = i
    return out
