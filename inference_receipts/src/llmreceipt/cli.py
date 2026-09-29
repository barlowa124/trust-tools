"""llmreceipt command line.

  llmreceipt capture --model HuggingFaceTB/SmolLM2-135M \
      --prompt "..." --out receipts.jsonl [--max-new-tokens 64]
  llmreceipt verify receipts.jsonl [--replay]
  llmreceipt show receipts.jsonl <receipt_id>
"""

from __future__ import annotations

import argparse
import json
import sys

from . import capture, verify
from .receipt import append_log, load_log


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="llmreceipt")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("capture", help="run a generation and append its receipt")
    s.add_argument("--model", required=True)
    s.add_argument("--prompt", required=True)
    s.add_argument("--out", required=True, help="receipt log (jsonl)")
    s.add_argument("--max-new-tokens", type=int, default=64)

    s = sub.add_parser("verify", help="check integrity, chain, and replay")
    s.add_argument("log")
    s.add_argument("--replay", action="store_true",
                   help="re-run each generation and compare output hashes")
    s.add_argument("--json", dest="json_out")

    s = sub.add_parser("show", help="print one receipt")
    s.add_argument("log")
    s.add_argument("receipt_id")

    a = p.parse_args(argv)

    if a.cmd == "capture":
        prev = None
        try:
            existing = load_log(a.out)
            prev = existing[-1] if existing else None
        except FileNotFoundError:
            pass
        r = capture.capture_hf(a.model, a.prompt,
                               max_new_tokens=a.max_new_tokens,
                               prev_receipt=prev)
        append_log(a.out, r)
        print(f"{r['receipt_id']}  {a.out}", file=sys.stderr)
        print(r["output"]["text"])
        return 0

    if a.cmd == "verify":
        receipts = load_log(a.log)
        rep = verify.verify_log(receipts, replay=a.replay)
        if a.json_out:
            open(a.json_out, "w", encoding="utf-8").write(
                json.dumps(rep, indent=2))
        status = "OK" if rep["ok"] else "PROBLEMS"
        print(f"{status}: {rep['n_receipts']} receipts, "
              f"{len(rep['problems'])} problem(s)")
        for p in rep["problems"]:
            print(f"  - {p}")
        if a.replay:
            for r in receipts:
                rb = r.get("replay", {})
                print(f"  {r['receipt_id']}: replay={rb.get('status')}")
        return 0 if rep["ok"] else 1

    if a.cmd == "show":
        for r in load_log(a.log):
            if r.get("receipt_id") == a.receipt_id:
                print(json.dumps(r, indent=2, ensure_ascii=False))
                return 0
        print(f"receipt {a.receipt_id} not found", file=sys.stderr)
        return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
