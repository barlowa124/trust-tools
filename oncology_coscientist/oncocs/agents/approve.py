"""Human approval gate for agent reports."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from oncocs.agents.graph import UNAPPROVED_BANNER


def _verified_report(agent_run_path: Path, record: dict, action: str):
    """Return (report_path, report_text, embedded run sha) after proving the
    report on disk is the one the run rendered.

    Two checks: the embedded marker must match the current agent_run.json
    content hash, and the file bytes must match the sha256 recorded at render
    time. The second check is what stops prose edits that keep the marker."""
    report_path = agent_run_path.parent / "report.md"
    report = report_path.read_text(encoding="utf-8")
    m = re.search(r"<!-- agent_run_sha256: ([0-9a-f]+) -->", report)
    if not m:
        raise ValueError("report.md missing recorded agent_run hash")
    from oncocs.agents.graph import agent_run_sha
    if agent_run_sha(record) != m.group(1):
        raise ValueError(f"agent_run.json changed since report was rendered. "
                         f"Refusing {action}")
    recorded = record.get("final_report_sha256")
    if recorded is not None:
        current = hashlib.sha256(report.encode("utf-8")).hexdigest()
        if current != recorded:
            raise ValueError(f"report.md changed since it was rendered. "
                             f"Refusing {action} on a modified report")
    return report_path, report, m.group(1)


def _stamp_banner(report: str, banner: str) -> str:
    if UNAPPROVED_BANNER in report:
        return report.replace(UNAPPROVED_BANNER, banner, 1)
    return re.sub(r"^> .*\n", banner + "\n", report, count=1)


def approve(agent_run_path: Path, by: str, note: str = "") -> Path:
    agent_run_path = Path(agent_run_path)
    record = json.loads(agent_run_path.read_text(encoding="utf-8"))
    if record.get("status") != "draft_pending_approval":
        raise ValueError(f"Cannot approve run with status {record.get('status')!r}")
    if record.get("approval"):
        raise ValueError("Run already approved")
    if record.get("human_review"):
        raise ValueError(f"Run already has a human decision: "
                         f"{record['human_review']['decision']!r}")

    report_path, report, run_sha = _verified_report(agent_run_path, record,
                                                    "approval")
    ts = datetime.now(UTC).isoformat()
    banner = f"> Approved by {by} on {ts[:10]}"
    report = _stamp_banner(report, banner)
    approval = {"by": by, "timestamp": ts, "agent_run_sha256": run_sha,
                "report_sha256": hashlib.sha256(report.encode("utf-8")).hexdigest()}
    if note:
        approval["note"] = note
    record["approval"] = approval
    agent_run_path.write_text(json.dumps(record, indent=2, default=str) + "\n",
                            encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    return report_path


def reject(agent_run_path: Path, by: str, reason: str) -> Path:
    agent_run_path = Path(agent_run_path)
    record = json.loads(agent_run_path.read_text(encoding="utf-8"))
    if record.get("approval"):
        raise ValueError("Run already approved; cannot reject")
    if record.get("human_review"):
        raise ValueError(f"Run already has a human decision: "
                         f"{record['human_review']['decision']!r}")
    report_path, report, run_sha = _verified_report(agent_run_path, record,
                                                    "rejection")
    ts = datetime.now(UTC).isoformat()
    banner = f"> **REJECTED BY HUMAN REVIEWER ({by})** - {reason}"
    report = _stamp_banner(report, banner)
    record["human_review"] = {"decision": "rejected", "by": by,
                              "timestamp": ts,
                              "reason": reason,
                              "agent_run_sha256": run_sha,
                              "report_sha256":
                                  hashlib.sha256(report.encode("utf-8")).hexdigest()}
    agent_run_path.write_text(json.dumps(record, indent=2, default=str) + "\n",
                            encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    return report_path
