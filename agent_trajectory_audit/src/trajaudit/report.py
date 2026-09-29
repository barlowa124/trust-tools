"""Audit report rendering: markdown for humans, JSON for machines."""

from __future__ import annotations

import json
from collections import Counter

from .model import Event

SEVERITY = {
    "verification_claim_gap": "high",
    "completion_without_verification": "medium",
    "abandoned_items": "medium",
    "plan_drift": "low",
    "scope_drift": "low",
    "unplanned_work": "low",
}


def build_report(events: list[Event], findings: list[dict],
                 session: str = "") -> dict:
    counts = Counter(f["detector"] for f in findings)
    return {
        "session": session or (events[0].session if events else ""),
        "n_events": len(events),
        "event_kinds": Counter(e.kind for e in events),
        "n_findings": len(findings),
        "by_detector": dict(counts),
        "findings": [{**f, "severity": SEVERITY.get(f["detector"], "low")}
                     for f in findings],
    }


def to_json(report: dict) -> str:
    r = dict(report)
    r["event_kinds"] = dict(r["event_kinds"])
    return json.dumps(r, indent=2, ensure_ascii=False)


def to_markdown(report: dict) -> str:
    lines = [
        "# Trajectory audit report",
        "",
        f"- Session: `{report['session']}`",
        f"- Events: {report['n_events']} "
        f"({', '.join(f'{v} {k}' for k, v in report['event_kinds'].items())})",
        f"- Findings: {report['n_findings']}",
        "",
        "| Detector | Findings |",
        "|---|---|",
    ]
    for det in ("verification_claim_gap", "completion_without_verification",
                "abandoned_items", "plan_drift", "scope_drift",
                "unplanned_work"):
        lines.append(f"| `{det}` | {report['by_detector'].get(det, 0)} |")
    lines += [
        "",
        "Findings are deterministic heuristics, not verdicts. Each links to",
        "event indices (`event_i`) in the trajectory for human review.",
        "",
        "## Findings",
        "",
    ]
    for f in report["findings"]:
        lines.append(f"- **[{SEVERITY.get(f['detector'], 'low')}]** "
                     f"`{f['detector']}` @ event {f['event_i']}: "
                     f"{f['summary']}")
        for e in f.get("evidence", []):
            lines.append(f"  - `{' '.join(str(e).split())[:200]}`")
    if not report["findings"]:
        lines.append("No findings.")
    lines.append("")
    return "\n".join(lines)
