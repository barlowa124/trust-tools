"""rcptreport command line.

  rcptreport build LOG.jsonl [LOG2.jsonl ...] --out report.md
      [--title "Checkpoint assessment"]
"""

from __future__ import annotations

import argparse
import sys

from .report import render


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="rcptreport")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("build", help="render a markdown audit report")
    s.add_argument("logs", nargs="+")
    s.add_argument("--out", default="-")
    s.add_argument("--title", default="Audit report")
    a = p.parse_args(argv)

    if a.cmd == "build":
        md = render(a.logs, title=a.title)
        if a.out == "-":
            sys.stdout.write(md)
        else:
            with open(a.out, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"wrote {a.out}", file=sys.stderr)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
