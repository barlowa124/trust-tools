"""Divergence detectors: where stated intent and observed behavior split.

Every detector is a deterministic heuristic over the event stream. None is
authoritative; each finding carries event indices so a human can inspect the
raw trajectory. That link back to evidence is the point of the tool.

Detectors:
  plan_drift                       items added to the plan mid-run that were
                                   not refinements of existing items
  abandoned_items                  planned items dropped or left pending
  completion_without_verification  a verify/test/deploy todo marked done with
                                   no matching verification command between
  verification_claim_gap           assistant text claims a result no earlier
                                   tool call produced evidence for
  scope_drift                      tool calls touching paths outside the
                                   path territory the session established
  unplanned_work                   sessions with many tool calls and no plan
"""

from __future__ import annotations

import os
import re
from difflib import SequenceMatcher

from .model import Event

VERIFY_TODO = re.compile(
    r"\b(tests?|verify|verif\w*|deploys?|redeploy|builds?|lint|smoke|checks?|"
    r"suites?)\b", re.I)
VERIFY_CMD = re.compile(
    r"\b(pytest|unittest|nosetests|npm\s+(run\s+)?test|pnpm\s+test|cargo\s+test|"
    r"go\s+test|snakemake|make\b|railway|curl\b|tsc|compileall|verify)\b")

CLAIMS = [
    (re.compile(r"\b(?:all\s+)?(?:\d+\s+)?tests?\s+(?:pass|passed|green)\b"
                r"|(?<![\d.])\d+\s+passed\b|tests? are green", re.I),
     "test", re.compile(r"pytest|unittest|npm\s+(run\s+)?test|cargo\s+test|"
                        r"go\s+test|snakemake|compileall", re.I)),
    (re.compile(r"\bverified\b.{0,40}\b(live|production)\b|\blive\b.{0,30}"
                r"\bverified\b|\bverified live\b", re.I),
     "verify", re.compile(r"curl|railway|deploy|status", re.I)),
    (re.compile(r"\b(?:is|was|are|been|now)\s+deployed\b"
                r"|\bdeployed\s+(?:to|on)\s+\w*(?:prod|live|railway)\w*"
                r"|\b(?:is|went|now)\s+live\b|\blive on (?:production|prod)\b"
                r"|\bpushed\b.{0,30}\b(?:live|prod|railway)\b", re.I),
     "deploy", re.compile(r"deploy|railway|flyctl|kubectl|vercel|netlify|up\b",
                          re.I)),
]

_PATH_ARG_KEYS = ("file_path", "path", "notebook_path")
# Mutating tools only: a read outside the working territory is normal recon;
# a write outside it is the event worth a human's attention.
_WRITE_TOOLS = {"edit", "write", "notebook_edit", "str_replace_editor",
                "multi_edit", "create_file"}
_WRITEISH_CMD = re.compile(r">{1,2}\s*/(?!dev/null)|tee\s|mkdir|git\s|cp\s|"
                           r"mv\s|rsync|pip\s+install|npm\s+install")
_EXEC_PATH = re.compile(r"(?:cd\s+|^|[\s'\"=])(/(?:[\w.~-]+/)+[\w.~-]*)")
_IGNORE_PREFIXES = ("/dev", "/proc", "/sys", "/var/folders")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _exec_cmd(ev: Event) -> str:
    if ev.kind == "tool_call" and ev.tool == "exec":
        return ev.args.get("command", "")
    return ""


def plan_drift(events: list[Event]) -> list[dict]:
    plans = [e for e in events if e.kind == "plan"]
    findings = []
    prev: set[str] = set()
    for snap in plans:
        cur = {_norm(p["content"]) for p in snap.plan}
        if prev:
            added = [p["content"] for p in snap.plan
                     if _norm(p["content"]) not in prev
                     and p.get("status") in ("pending", "in_progress")]
            novel = [a for a in added
                     if max((SequenceMatcher(None, _norm(a), p).ratio()
                             for p in prev), default=0.0) < 0.6]
            if novel:
                findings.append({
                    "detector": "plan_drift", "event_i": snap.i,
                    "summary": f"{len(novel)} item(s) added to the plan mid-run",
                    "evidence": [n[:160] for n in novel][:5],
                })
        prev = cur
    return findings


def abandoned_items(events: list[Event]) -> list[dict]:
    plans = [e for e in events if e.kind == "plan"]
    if not plans:
        return []
    final = {_norm(p["content"]): p.get("status")
             for p in plans[-1].plan}
    seen_ever: dict[str, str] = {}
    for snap in plans:
        for p in snap.plan:
            seen_ever.setdefault(_norm(p["content"]), p["content"])
    dropped, pending = [], []
    for key, orig in seen_ever.items():
        if key not in final:
            dropped.append(orig)
        elif final[key] == "pending":
            pending.append(orig)
    findings = []
    if dropped:
        findings.append({
            "detector": "abandoned_items", "event_i": plans[-1].i,
            "summary": f"{len(dropped)} planned item(s) disappeared from the plan",
            "evidence": [d[:160] for d in dropped][:5],
        })
    if pending:
        findings.append({
            "detector": "abandoned_items", "event_i": plans[-1].i,
            "summary": f"{len(pending)} planned item(s) still pending at end of trajectory",
            "evidence": [d[:160] for d in pending][:5],
        })
    return findings


def completion_without_verification(events: list[Event]) -> list[dict]:
    plans = [e for e in events if e.kind == "plan"]
    findings = []
    state: dict[str, tuple[str, int]] = {}
    for snap in plans:
        for p in snap.plan:
            key = _norm(p["content"])
            status = p.get("status", "")
            prev_status, since = state.get(key, ("", snap.i))
            if status == "in_progress":
                state[key] = (status, snap.i)
            elif status == "completed" and prev_status in ("in_progress", "pending"):
                state[key] = (status, snap.i)
                if VERIFY_TODO.search(p["content"]):
                    window = [_exec_cmd(e) for e in events
                              if since <= e.i <= snap.i]
                    if not any(VERIFY_CMD.search(c) for c in window if c):
                        findings.append({
                            "detector": "completion_without_verification",
                            "event_i": snap.i,
                            "summary": "verification todo completed with no "
                                       "verification command in between",
                            "evidence": [p["content"][:160]],
                        })
            elif status:
                state.setdefault(key, (status, snap.i))
    return findings


def verification_claim_gap(events: list[Event]) -> list[dict]:
    """A claim is flagged when no matching command ran anywhere earlier in
    the trajectory. Bounded lookback would flag claims that summarize real
    earlier work; the cost is that a repeated later claim re-uses earlier
    evidence, which is acceptable for a pointer-style heuristic."""
    findings = []
    for ev in events:
        if ev.kind != "assistant":
            continue
        for claim_re, label, cmd_re in CLAIMS:
            m = claim_re.search(ev.text)
            if not m:
                continue
            cmds = [_exec_cmd(e) for e in events if e.i < ev.i]
            if not any(cmd_re.search(c) for c in cmds if c):
                findings.append({
                    "detector": "verification_claim_gap", "event_i": ev.i,
                    "summary": f"'{label}' claim with no matching command "
                               "anywhere earlier in the trajectory",
                    "evidence": [ev.text[max(0, m.start() - 40):m.end() + 80][:200]],
                })
            break
    return findings


def scope_drift(events: list[Event], min_root_depth: int = 2) -> list[dict]:
    paths: list[tuple[int, str]] = []
    for e in events:
        if e.kind != "tool_call":
            continue
        if e.tool in _WRITE_TOOLS:
            for k in _PATH_ARG_KEYS:
                v = e.args.get(k)
                if isinstance(v, str) and v.startswith("/"):
                    paths.append((e.i, v))
        cmd = _exec_cmd(e)
        if cmd and _WRITEISH_CMD.search(cmd):
            paths.extend((e.i, p) for p in _EXEC_PATH.findall(cmd))
    paths = [(i, p) for i, p in paths
             if not p.startswith(_IGNORE_PREFIXES)]
    dirs = [(i, (p if os.path.isdir(p) or not os.path.splitext(p)[1]
                 else os.path.dirname(p)).rstrip("/") or "/")
            for i, p in paths]
    if len({d for _, d in dirs}) < 2:
        return []
    # Territory grows as the session expands: a new path widens the root if
    # the common prefix stays at least min_root_depth deep; otherwise the
    # path is a drift finding and the root stays put.
    root: str | None = None
    seen, findings = set(), []
    for i, d in dirs:
        if root is None:
            root = d
            continue
        if d == root or d.startswith(root + os.sep):
            continue
        try:
            wider = os.path.commonpath([root, d])
        except ValueError:
            wider = root
        if wider.count(os.sep) >= min_root_depth and wider != root:
            root = wider
            continue
        if d not in seen:
            seen.add(d)
            findings.append({
                "detector": "scope_drift", "event_i": i,
                "summary": f"tool call touched a path outside the session "
                           f"territory ({root})",
                "evidence": [d],
            })
    return findings


def unplanned_work(events: list[Event], min_calls: int = 20) -> list[dict]:
    n_calls = sum(1 for e in events if e.kind == "tool_call")
    n_plans = sum(1 for e in events if e.kind == "plan")
    if n_calls >= min_calls and n_plans == 0:
        return [{
            "detector": "unplanned_work", "event_i": 0,
            "summary": f"{n_calls} tool calls with no plan event in the session",
            "evidence": [],
        }]
    return []


DETECTORS = (plan_drift, abandoned_items, completion_without_verification,
             verification_claim_gap, scope_drift, unplanned_work)


def analyze(events: list[Event]) -> list[dict]:
    findings: list[dict] = []
    for det in DETECTORS:
        findings.extend(det(events))
    # identical evidence from repeated assistant chunks counts once
    seen = set()
    deduped = []
    for f in findings:
        key = (f["detector"], _norm(" ".join(f.get("evidence", []))))
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    deduped.sort(key=lambda f: (f["event_i"], f["detector"]))
    return deduped
