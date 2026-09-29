"""Monitor policy: ordered rules over (tool, args) -> verdict.

A policy file is JSON:
  {
    "defaults": {"action": "allow"},
    "rules": [
      {"id": "no-rm-rf", "tool": "exec",
       "arg_regex": "rm\\s+-rf", "action": "deny", "severity": "high",
       "reason": "recursive delete"},
      {"id": "writes-in-scope", "tool": "write",
       "arg_field": "file_path", "path_scope": ["./", "src/"],
       "action": "deny_outside", "severity": "medium"}
    ]
  }

Actions: allow | flag | deny. `deny_outside` denies when a path arg
escapes every listed scope (normalized, so `a/../escape` resolves).
Verdict precedence is deny > flag > allow; first deny wins.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

ACTIONS = ("allow", "flag", "deny")


@dataclass
class Verdict:
    action: str           # allow | flag | deny
    rule: str | None      # rule id that produced it
    severity: str
    reason: str


def load_policy(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        pol = json.load(f)
    for i, r in enumerate(pol.get("rules", [])):
        if "id" not in r or "action" not in r:
            raise ValueError(f"rule[{i}] needs id and action")
        if r["action"] not in ACTIONS + ("deny_outside",):
            raise ValueError(f"rule[{i}] bad action {r['action']!r}")
        if "arg_regex" in r:
            re.compile(r["arg_regex"])
    return pol


def _norm(p: str) -> str:
    return os.path.normpath(os.path.abspath(os.path.expanduser(p)))


def _args_text(args: Any) -> str:
    if isinstance(args, dict):
        return json.dumps(args)
    return str(args)


def _in_scope(path: str, scopes: list[str], cwd: str) -> bool:
    t = _norm(path)
    for s in scopes:
        base = _norm(os.path.join(cwd, s)) if not os.path.isabs(s) else _norm(s)
        if t == base or t.startswith(base + os.sep):
            return True
    return False


def evaluate(pol: dict, tool: str, args: Any, cwd: str = ".") -> Verdict:
    """First matching deny wins; else first flag; else default."""
    default = pol.get("defaults", {}).get("action", "allow")
    flagged: Verdict | None = None
    for r in pol.get("rules", []):
        if r.get("tool") and r["tool"] != tool:
            continue
        matched = True
        if "arg_regex" in r:
            matched = re.search(r["arg_regex"], _args_text(args)) is not None
        if matched and r["action"] == "deny_outside":
            fld = r.get("arg_field", "file_path")
            path = args.get(fld) if isinstance(args, dict) else str(args)
            if path is None:
                matched = False
            else:
                matched = not _in_scope(path, r.get("path_scope", []), cwd)
        if not matched:
            continue
        action = "deny" if r["action"] == "deny_outside" else r["action"]
        v = Verdict(action, r["id"], r.get("severity", "low"),
                    r.get("reason", r["id"]))
        if action == "deny":
            return v
        if action == "flag" and flagged is None:
            flagged = v
    if flagged:
        return flagged
    return Verdict(default, None, "none", "default")
