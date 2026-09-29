"""Eval task specs: a JSON list of graded prompts.

Each task:
  {
    "id":     "unique id",
    "prompt": "the literal prompt text sent to the model",
    "grader": {"kind": "exact"|"contains"|"not_contains"|"regex"|"abstain",
               "value": "..."},
    "tag":    "probe class for per-class aggregation"
  }

Graders are deterministic string checks — no LLM-as-judge. If a probe
needs judgment, write it as an explicit label the grader can check for.
"""

from __future__ import annotations

import json
import re

GRADER_KINDS = ("exact", "contains", "not_contains", "regex", "abstain")


def load_tasks(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        tasks = json.load(f)
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("task spec must be a non-empty JSON list")
    seen = set()
    for i, t in enumerate(tasks):
        for k in ("id", "prompt", "grader", "tag"):
            if k not in t:
                raise ValueError(f"task[{i}] missing {k!r}")
        if t["id"] in seen:
            raise ValueError(f"duplicate task id {t['id']!r}")
        seen.add(t["id"])
        g = t["grader"]
        if g.get("kind") not in GRADER_KINDS:
            raise ValueError(f"task[{i}] unknown grader kind {g.get('kind')!r}")
        if g["kind"] != "abstain" and "value" not in g:
            raise ValueError(f"task[{i}] grader needs 'value'")
        if g["kind"] == "regex":
            re.compile(g["value"])
    return tasks
