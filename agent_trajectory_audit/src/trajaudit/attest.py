"""Attested finding log: each audit finding as a hash-chained record.

Same canonical-JSON chain envelope as the sibling `llmreceipt` package
(inference_receipts/ in this monorepo): the record id is derived from the
sha256 of its canonical body, and `chain_prev` links to the previous
record's id. The construction is vendored here (stdlib only) so trajaudit
stays dependency-free; the monorepo-level test
`trust-tools/tests/test_interop.py` re-verifies emitted logs using
llmreceipt's own `canonical_json`/`sha256_bytes` primitives, proving the
formats agree.

An attested log makes a finding list tamper-evident: reorder, edit, or drop
a finding and the chain check fails.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = 1


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def attest_report(report: dict, report_sha: str | None = None) -> list[dict]:
    """Return one hash-chained record per finding in an audit report."""
    if report_sha is None:
        report_sha = sha256_bytes(canonical_json(report))
    records = []
    prev_id = "genesis"
    for f in report.get("findings", []):
        body = {
            "v": SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "kind": "audit_finding",
            "session": report.get("session", ""),
            "report_sha256": report_sha,
            "finding": f,
            "chain_prev": prev_id,
        }
        body["finding_id"] = "fnd-" + sha256_bytes(canonical_json(body))[:16]
        records.append(body)
        prev_id = body["finding_id"]
    return records


def record_hash(record: dict) -> str:
    body = {k: v for k, v in record.items() if k != "finding_id"}
    return "fnd-" + sha256_bytes(canonical_json(body))[:16]


def check_log(records: list[dict]) -> list[str]:
    """Return integrity problems in an attested finding log."""
    problems = []
    prev_id = "genesis"
    for i, r in enumerate(records):
        rid = r.get("finding_id", "?")
        if record_hash(r) != rid:
            problems.append(f"[{i}] {rid}: content hash does not match "
                            "finding_id (body tampered)")
        if r.get("chain_prev") != prev_id:
            problems.append(f"[{i}] {rid}: chain break (expected prev="
                            f"{prev_id}, got {r.get('chain_prev')})")
        if i and r.get("report_sha256") != records[0].get("report_sha256"):
            problems.append(f"[{i}] {rid}: report_sha256 differs from "
                            "first record (mixed logs)")
        prev_id = rid
    return problems
