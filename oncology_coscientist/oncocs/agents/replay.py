"""Replay an agent run from its transcript and compare outputs."""
from __future__ import annotations

import json
import re
from pathlib import Path

from oncocs.agents.graph import AgentState, build_graph, render_report_md
from oncocs.llm.recorded import RecordedBackend, TranscriptMismatch


def replay_agent(agent_run_path: Path) -> tuple[str, str]:
    """Return (status, message) where status is PASS, FAIL, or FROZEN.
    FROZEN means the recorded prompts no longer match what the current code
    issues. The run predates a prompt change and is preserved as evidence."""
    agent_run_path = Path(agent_run_path)
    record = json.loads(agent_run_path.read_text(encoding="utf-8"))
    results = json.loads(Path(record["results_path"]).read_text(encoding="utf-8"))
    # results/<cohort>/<run_id>/agent/<agent_run_id>/agent_run.json
    root = agent_run_path.parents[5]

    from oncocs.config import load_cohort
    from oncocs.splits import load_split
    cohort = record.get("cohort", results["cohort"])
    backend = RecordedBackend(record["transcript"])
    graph = build_graph(backend, seed=record.get("seed"))
    init: AgentState = {"cohort": cohort,
                        "results_path": record["results_path"],
                        "root": str(root), "results": results,
                        "split": load_split(load_cohort(cohort, root), root),
                        "drafts": [], "attempts": 0, "status": "running"}
    try:
        final = graph.invoke(init)
    except TranscriptMismatch as exc:
        m2 = re.search(r"(?:index|call) (\d+)", str(exc))
        return "FROZEN", (m2.group(1) if m2 else "?")

    report_path = agent_run_path.parent / "report.md"
    original_md = report_path.read_text(encoding="utf-8")

    m = re.search(r"<!-- agent_run_sha256: ([0-9a-f]+) -->", original_md)
    if record.get("status") in ("rejected", "abstained"):
        expected = render_report_md(final.get("draft", ""),
                                    agent_run_sha256=m.group(1) if m else None,
                                    status=record["status"],
                                    drafts=record.get("drafts", []))
        body_ok = original_md == expected
    else:
        # report.md embeds the pre-approval agent_run sha + optional approval banner;
        # compare the draft body and the verification outcome.
        orig_body = original_md.split("\n\n", 1)[-1] if "\n\n" in original_md else original_md
        replay_body = final.get("draft", "") + "\n"
        body_ok = orig_body.strip() == replay_body.strip()
    ver_ok = final.get("verification") == record.get("verification")
    status_ok = final.get("status") == record.get("status")
    if body_ok and ver_ok and status_ok:
        return "PASS", "report bytes and verification identical"
    diffs = []
    if not body_ok:
        diffs.append("draft differs")
    if not ver_ok:
        diffs.append("verification differs")
    if not status_ok:
        diffs.append(f"status {final.get('status')} != {record.get('status')}")
    return "FAIL", "; ".join(diffs)
