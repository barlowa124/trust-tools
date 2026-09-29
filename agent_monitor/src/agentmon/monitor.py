"""Live monitor: intercept tool calls before they run.

`Monitor.check(tool, args)` returns a Verdict; `Monitor.gate` raises
DenyError on deny. `Monitor.wrap(fn)` returns a drop-in wrapper that gates
each call and appends a hash-chained alert record for every flag or deny
(allows are optionally logged too — off by default, since quiet-allow
logs drown the signal).

Alert records use the same canonical-JSON chain envelope as llmreceipt
and trajaudit.attest: record id derives from the content hash, chain_prev
links the previous record.
"""

from __future__ import annotations

import functools
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable

from .chainfmt import canonical_json, sha256_bytes, sha256_text
from .policy import evaluate, Verdict

SCHEMA_VERSION = 1


class DenyError(Exception):
    def __init__(self, verdict: Verdict):
        super().__init__(f"denied by {verdict.rule}: {verdict.reason}")
        self.verdict = verdict


class Monitor:
    def __init__(self, policy: dict, *, cwd: str = ".",
                 log_allows: bool = False):
        self.policy = policy
        self.cwd = cwd
        self.log_allows = log_allows
        self.records: list[dict] = []
        self._prev_id = "genesis"

    def check(self, tool: str, args: Any) -> Verdict:
        return evaluate(self.policy, tool, args, self.cwd)

    def _record(self, tool: str, args: Any, v: Verdict) -> dict:
        body = {
            "v": SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "kind": "monitor_alert",
            "tool": tool,
            "args_sha256": sha256_text(_args_text(args)),
            "verdict": {"action": v.action, "rule": v.rule,
                        "severity": v.severity, "reason": v.reason},
            "chain_prev": self._prev_id,
        }
        body["alert_id"] = "alm-" + sha256_bytes(canonical_json(body))[:16]
        self.records.append(body)
        self._prev_id = body["alert_id"]
        return body

    def gate(self, tool: str, args: Any) -> Verdict:
        """Evaluate and enforce: raises on deny, records flags/denies."""
        v = self.check(tool, args)
        if v.action == "deny":
            self._record(tool, args, v)
            raise DenyError(v)
        if v.action == "flag" or (v.action == "allow" and self.log_allows):
            self._record(tool, args, v)
        return v

    def wrap(self, tool: str, arg_fn: Callable | None = None):
        """Decorator: gate each call through `check` before running."""
        def deco(fn):
            @functools.wraps(fn)
            def inner(*a, **kw):
                args = arg_fn(*a, **kw) if arg_fn else (
                    kw or (a[0] if len(a) == 1 else a))
                self.gate(tool, args)
                return fn(*a, **kw)
            return inner
        return deco

    def flush(self, path: str) -> None:
        with open(path, "a", encoding="utf-8") as f:
            for r in self.records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        self.records.clear()


def _args_text(args: Any) -> str:
    if isinstance(args, dict):
        return json.dumps(args, sort_keys=True)
    return str(args)


def record_hash(record: dict) -> str:
    body = {k: v for k, v in record.items() if k != "alert_id"}
    return "alm-" + sha256_bytes(canonical_json(body))[:16]


def check_log(records: list[dict]) -> list[str]:
    problems = []
    prev = "genesis"
    for i, r in enumerate(records):
        rid = r.get("alert_id", "?")
        if record_hash(r) != rid:
            problems.append(f"[{i}] {rid}: content hash mismatch")
        if r.get("chain_prev") != prev:
            problems.append(f"[{i}] {rid}: chain break")
        prev = rid
    return problems
