"""agentmon command line.

  agentmon check --policy p.json --tool exec --args-json '{"command":"ls"}'
  agentmon verify log.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys

from .monitor import Monitor, check_log
from .policy import load_policy


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="agentmon")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("check", help="evaluate one tool call")
    s.add_argument("--policy", required=True)
    s.add_argument("--tool", required=True)
    s.add_argument("--args-json", required=True)
    s.add_argument("--cwd", default=".")

    s = sub.add_parser("verify", help="check an alert log's chain")
    s.add_argument("log")

    a = p.parse_args(argv)

    if a.cmd == "check":
        pol = load_policy(a.policy)
        m = Monitor(pol, cwd=a.cwd)
        v = m.check(a.tool, json.loads(a.args_json))
        print(json.dumps({"action": v.action, "rule": v.rule,
                          "severity": v.severity, "reason": v.reason},
                         indent=1))
        return {"deny": 2, "flag": 1}.get(v.action, 0)

    if a.cmd == "verify":
        records = [json.loads(l) for l in open(a.log) if l.strip()]
        problems = check_log(records)
        for x in problems:
            print(x, file=sys.stderr)
        print(f"{len(records)} records, "
              f"{'OK' if not problems else f'{len(problems)} problems'}",
              file=sys.stderr)
        return 0 if not problems else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
