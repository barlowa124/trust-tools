"""agentob — trace ingestion, policy enrichment, and trace reports.

  agentob report TRACE.json [--policy POLICY.json] [--cwd DIR]
                 [--html OUT.html] [--events OUT.jsonl]
                 [--alerts OUT.jsonl]

Reads a span trace (flat schema or OTLP-lite export), gates every
tool_call span through the policy, converts the trace to trajaudit
events and runs the detectors, then renders a report. Default output
is markdown on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _default_policy():
    try:
        from agentmon.redteam import default_policy_path
        from agentmon.policy import load_policy
        return load_policy(default_policy_path())
    except ImportError:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agentob", description=__doc__)
    ap.add_argument("command", choices=["report"])
    ap.add_argument("trace")
    ap.add_argument("--policy", default=None)
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--html", default=None)
    ap.add_argument("--events", default=None)
    ap.add_argument("--alerts", default=None)
    args = ap.parse_args(argv)

    from . import spans, enrich, render
    trace = spans.load(args.trace)

    monitor = None
    policy = None
    if args.policy:
        from agentmon.policy import load_policy
        policy = load_policy(args.policy)
    else:
        policy = _default_policy()
    if policy is not None:
        try:
            from agentmon.monitor import Monitor
            monitor = Monitor(policy, cwd=args.cwd, log_allows=False)
        except ImportError:
            policy = None
    if policy is None:
        print("agentmon not importable; verdicts skipped",
              file=sys.stderr)

    verdicts = enrich.gate_spans(trace, policy, cwd=args.cwd,
                                 monitor=monitor) if policy else None
    events = enrich.to_events(trace)
    findings = enrich.audit(events)

    report = {"trace": Path(args.trace).name, "spans": trace,
              "verdicts": verdicts, "findings": findings}

    if args.events:
        with open(args.events, "w") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
    if args.alerts:
        if monitor is not None:
            monitor.flush(args.alerts)
        else:
            Path(args.alerts).write_text("")

    if args.html:
        Path(args.html).write_text(render.render_html(report))
    else:
        sys.stdout.write(render.render_md(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
