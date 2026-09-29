"""Markdown report for a battery results.json."""

from __future__ import annotations

import json


def render_md(summary: dict) -> str:
    lines = [
        "# agent_sandbox battery report",
        "",
        f"Battery: `{summary['battery']}` — "
        f"{summary['n_scenarios']} scenarios, "
        f"{summary['n_contained']} contained.",
        "",
        "| scenario | kind | verdicts | outcome | contained |",
        "|---|---|---|---|---|",
    ]
    for r in summary["results"]:
        outs = ", ".join(sorted({s["outcome"] for s in r["steps"]}))
        verdicts = ", ".join(sorted({s["verdict"] for s in r["steps"]}))
        mark = "yes" if r["contained"] else "**NO**"
        if r["expect"] == "not_contained":
            mark = "no (residual)"
        lines.append(f"| `{r['id']}` | {r['kind']} | {verdicts} "
                     f"| {outs} | {mark} |")
    lines += ["", "## Findings", ""]
    any_f = False
    for r in summary["results"]:
        for f in r["findings"]:
            lines.append(f"- `{r['id']}`: {f}")
            any_f = True
    if not any_f:
        lines.append("none")
    if summary["mismatches"]:
        lines += ["", "## Mismatches", ""]
        for m in summary["mismatches"]:
            lines.append(f"- `{m['id']}`: expected {m['expect']}, "
                         f"got contained={m['contained']}")
    lines += [
        "",
        "Containment means every scripted call was either denied by the",
        "policy gate, blocked by the jail's realpath check, or honestly",
        "stayed inside the jail scope. `no (residual)` marks the",
        "documented gap: non-redirect writes (cp/mv) are not redirect",
        "targets the gate extracts, and without bubblewrap the exec",
        "path is not kernel-isolated, so the copy reaches the host.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    summary = json.load(open("results/results.json"))
    with open("results/report.md", "w") as f:
        f.write(render_md(summary))
    print("wrote results/report.md")
