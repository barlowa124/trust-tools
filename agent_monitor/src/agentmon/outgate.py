"""Output-side policy: rules over the agent's emitted text.

Tool-call rules stop a bad *action* before it lands; output rules stop
a bad *answer* before it leaves the loop: secret-shaped strings,
unparseable structure where JSON was promised, missing required keys,
field values outside a declared contract, over-length emission.

The policy file's "output_rules" list uses the same verdict shape and
precedence as input rules (deny > flag > allow; first deny wins):

  {"id": "no-token-leak", "squash_regex": "sk-[A-Za-z0-9]{20,}",
   "action": "deny", "severity": "high", "reason": "token-shaped output"},
  {"id": "structured-answer", "format": "json",
   "require_keys": ["answer", "citations"],
   "action": "deny", "severity": "medium",
   "reason": "answer must be JSON with answer+citations"},
  {"id": "verbosity", "max_chars": 4000, "action": "flag",
   "severity": "low", "reason": "over-length response"}

Matchers a rule can carry (each states a violation condition; the rule
fires on the first that trips — OR semantics):

  text_regex          fires when the pattern appears in the raw output
  text_regex_require  fires when the pattern is ABSENT
  squash_regex        fires when the pattern appears in the output with
                      every whitespace char removed — catches secrets
                      split across spaces ("sk- AbCd..."). Boundaries do
                      not exist in squashed text; write self-delimiting
                      patterns and expect occasional false positives.
  max_chars           fires when len(output) exceeds the cap
  format: "json"      fires when the output does not parse as JSON
  require_keys        fires when the parsed JSON object lacks a key
  fields              per-key contract on the parsed JSON object:
                      {"name": {"type": "str"|"int"|"number"|"bool"|
                                "list"|"dict", "required": bool,
                                "enum": [...], "min": n, "max": n,
                                "min_len": n, "max_len": n,
                                "pattern": regex}}

Structured matchers skip silently on non-JSON output — pair them with
format: "json" when structure is mandatory. Evasion note: squash and
regex matching catch *known* token shapes; an encoded or reworded
secret has no shape to match. That boundary is exercised in the output
battery, not hidden.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .policy import Verdict

_TYPES = {
    "str": str, "int": int, "number": (int, float),
    "bool": bool, "list": list, "dict": dict,
}


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _parse(text: Any) -> Any:
    if isinstance(text, str):
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return None
    return text if isinstance(text, (dict, list)) else None


def _field_errors(fields: dict, obj: Any) -> list[str]:
    """First-pass structural contract for agent JSON output. Deliberately
    narrower than JSON Schema — the shapes agents actually emit."""
    if not isinstance(obj, dict):
        return ["output is not a JSON object"]
    errs = []
    for name, spec in fields.items():
        val = obj.get(name)
        if val is None:
            if spec.get("required"):
                errs.append(f"{name}: required, missing")
            continue
        t = spec.get("type")
        if t:
            want = _TYPES.get(t)
            if want is None:
                errs.append(f"{name}: unknown type {t!r}")
            elif t == "int" and isinstance(val, bool):
                errs.append(f"{name}: bool is not int")
            elif not isinstance(val, want):
                errs.append(f"{name}: expected {t}")
                continue
        if "enum" in spec and val not in spec["enum"]:
            errs.append(f"{name}: not in enum")
        if "min" in spec and isinstance(val, (int, float)) \
                and not isinstance(val, bool) and val < spec["min"]:
            errs.append(f"{name}: below min {spec['min']}")
        if "max" in spec and isinstance(val, (int, float)) \
                and not isinstance(val, bool) and val > spec["max"]:
            errs.append(f"{name}: above max {spec['max']}")
        if "min_len" in spec and hasattr(val, "__len__") \
                and len(val) < spec["min_len"]:
            errs.append(f"{name}: shorter than {spec['min_len']}")
        if "max_len" in spec and hasattr(val, "__len__") \
                and len(val) > spec["max_len"]:
            errs.append(f"{name}: longer than {spec['max_len']}")
        if "pattern" in spec and isinstance(val, str) \
                and not re.search(spec["pattern"], val):
            errs.append(f"{name}: fails pattern")
    return errs


def _rule_violation(r: dict, text: str, obj: Any,
                    parsed: bool) -> str | None:
    """None when the rule does not fire; a short violation tag when it
    does — used as the verdict reason detail."""
    if "text_regex" in r and re.search(r["text_regex"], text, re.I):
        return "text_regex matched"
    if "text_regex_require" in r \
            and not re.search(r["text_regex_require"], text, re.I):
        return "required pattern absent"
    if "squash_regex" in r \
            and re.search(r["squash_regex"], _squash(text), re.I):
        return "squash_regex matched"
    if "max_chars" in r and len(text) > r["max_chars"]:
        return f"over {r['max_chars']} chars"
    if r.get("format") == "json" and not parsed:
        return "not JSON"
    if "require_keys" in r and parsed and isinstance(obj, dict):
        missing = [k for k in r["require_keys"] if k not in obj]
        if missing:
            return "missing keys: " + ",".join(missing)
    if "fields" in r and parsed:
        errs = _field_errors(r["fields"], obj)
        if errs:
            return "; ".join(errs[:3])
    return None


def evaluate_output(pol: dict, text: Any) -> Verdict:
    """First matching deny wins; else first flag; else default."""
    if not isinstance(text, str):
        text = json.dumps(text, sort_keys=True, default=str)
    obj = _parse(text)
    parsed = obj is not None
    default = pol.get("defaults", {}).get("action", "allow")
    flagged: Verdict | None = None
    for r in pol.get("output_rules", []):
        why = _rule_violation(r, text, obj, parsed)
        if why is None:
            continue
        action = r["action"]
        v = Verdict(action, r["id"], r.get("severity", "low"),
                    f"{r.get('reason', r['id'])} ({why})")
        if action == "deny":
            return v
        if action == "flag" and flagged is None:
            flagged = v
    if flagged:
        return flagged
    return Verdict(default, None, "none", "default")


def validate_output_rules(rules: list) -> None:
    """Same upfront failure style as load_policy: bad rules raise
    ValueError at load time, not at the first gated emission."""
    known = {"id", "action", "severity", "reason", "text_regex",
             "text_regex_require", "squash_regex", "max_chars",
             "format", "require_keys", "fields"}
    for i, r in enumerate(rules):
        if "id" not in r or "action" not in r:
            raise ValueError(f"output_rule[{i}] needs id and action")
        if r["action"] not in ("allow", "flag", "deny"):
            raise ValueError(
                f"output_rule[{i}] bad action {r['action']!r}")
        unknown = set(r) - known
        if unknown:
            raise ValueError(
                f"output_rule[{i}] unknown keys {sorted(unknown)}")
        for key in ("text_regex", "text_regex_require", "squash_regex"):
            if key in r:
                re.compile(r[key])
        if "format" in r and r["format"] != "json":
            raise ValueError(
                f"output_rule[{i}] format {r['format']!r} "
                "(only 'json')")
        for name, spec in r.get("fields", {}).items():
            t = spec.get("type")
            if t and t not in _TYPES:
                raise ValueError(
                    f"output_rule[{i}] field {name}: "
                    f"unknown type {t!r}")
            if "pattern" in spec:
                re.compile(spec["pattern"])
