"""trajaudit command line.

  trajaudit sessions --db ~/.local/share/devin/cli/sessions.db
  trajaudit ingest-devin --db <sessions.db> --session <id> --out t.jsonl
                         [--sanitize] [--window A:B]
  trajaudit sanitize in.jsonl --out clean.jsonl
  trajaudit audit t.jsonl [--json out.json] [--md out.md]
  trajaudit attest report.json --out findings.jsonl
  trajaudit verify-attest findings.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys

from . import attest, devin, detectors, report, sanitize as san
from .model import read_jsonl, write_jsonl


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="trajaudit")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sessions", help="list sessions in a devin sessions.db")
    s.add_argument("--db", required=True)

    s = sub.add_parser("ingest-devin", help="extract one session to JSONL")
    s.add_argument("--db", required=True)
    s.add_argument("--session", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--sanitize", action="store_true")
    s.add_argument("--window", default=None,
                   help="A:B slice of event indices to keep")

    s = sub.add_parser("sanitize", help="redact a trajectory JSONL")
    s.add_argument("trajectory")
    s.add_argument("--out", required=True)

    s = sub.add_parser("audit", help="run detectors on a trajectory JSONL")
    s.add_argument("trajectory")
    s.add_argument("--json", dest="json_out")
    s.add_argument("--md", dest="md_out")

    s = sub.add_parser("attest",
                       help="hash-chain a report's findings into JSONL")
    s.add_argument("report_json", help="audit report written by --json")
    s.add_argument("--out", required=True)

    s = sub.add_parser("verify-attest",
                       help="check an attested finding log's chain")
    s.add_argument("log")

    a = p.parse_args(argv)

    if a.cmd == "sessions":
        for s in devin.list_sessions(a.db):
            print(f"{s['id']}\t{s['created_at']}\t{(s['title'] or '')[:80]}")
        return 0

    if a.cmd == "ingest-devin":
        events = devin.ingest_session(a.db, a.session)
        if a.window:
            lo, _, hi = a.window.partition(":")
            events = events[int(lo):int(hi) if hi else None]
        if a.sanitize:
            events = san.sanitize(events)
        write_jsonl(events, a.out)
        print(f"wrote {len(events)} events -> {a.out}", file=sys.stderr)
        return 0

    if a.cmd == "sanitize":
        events = san.sanitize(read_jsonl(a.trajectory))
        write_jsonl(events, a.out)
        print(f"wrote {len(events)} events -> {a.out}", file=sys.stderr)
        return 0

    if a.cmd == "audit":
        events = read_jsonl(a.trajectory)
        findings = detectors.analyze(events)
        rep = report.build_report(events, findings)
        if a.json_out:
            open(a.json_out, "w", encoding="utf-8").write(report.to_json(rep))
        if a.md_out:
            open(a.md_out, "w", encoding="utf-8").write(report.to_markdown(rep))
        if not (a.json_out or a.md_out):
            print(report.to_markdown(rep))
        return 0

    if a.cmd == "attest":
        rep = json.loads(open(a.report_json, encoding="utf-8").read())
        records = attest.attest_report(rep)
        with open(a.out, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"attested {len(records)} findings -> {a.out}",
              file=sys.stderr)
        return 0

    if a.cmd == "verify-attest":
        records = [json.loads(l) for l in
                   open(a.log, encoding="utf-8") if l.strip()]
        problems = attest.check_log(records)
        for p in problems:
            print(p, file=sys.stderr)
        print(f"{len(records)} records, "
              f"{'OK' if not problems else f'{len(problems)} problems'}",
              file=sys.stderr)
        return 0 if not problems else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
