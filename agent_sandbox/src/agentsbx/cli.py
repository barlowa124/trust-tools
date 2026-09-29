"""agentsbx run --scenarios scenarios/battery.json --out-dir DIR [--report]

Runs the elicitation battery through agentmon + Jail and writes
results.json (and report.md with --report).
"""

from __future__ import annotations

import argparse
import json
import sys

from .report import render_md
from .runner import run_battery


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="agentsbx")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--scenarios", required=True)
    r.add_argument("--out-dir", required=True)
    r.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "run":
        summary = run_battery(a.scenarios, a.out_dir)
        if a.report:
            from pathlib import Path
            Path(a.out_dir, "report.md").write_text(
                render_md(summary))
        mism = summary["mismatches"]
        print(json.dumps({k: v for k, v in summary.items()
                          if k != "results"}, indent=1))
        return 1 if mism else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
