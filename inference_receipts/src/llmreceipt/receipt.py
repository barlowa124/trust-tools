"""Receipt model: a hash-bound record of one LLM call.

A receipt binds five things with hashes: the exact weights file, the exact
input text, the generation settings, the output text, and the previous
receipt in the log. Verifying a receipt means recomputing those hashes and,
optionally, re-running the generation to compare the output.

Canonical hashing is over JSON with sorted keys and no whitespace, so the
hash is stable across serializers that respect the schema.
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


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def sha256_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def make_receipt(*, backend: dict, model: dict, input_text: str,
                 generation: dict, output_text: str, gen_time_s: float,
                 n_new_tokens: int | None, prev_receipt: dict | None) -> dict:
    body = {
        "v": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backend": backend,
        "model": model,
        "input": {"text": input_text, "sha256": sha256_text(input_text)},
        "generation": generation,
        "output": {
            "text": output_text,
            "sha256": sha256_text(output_text),
            "n_new_tokens": n_new_tokens,
            "gen_time_s": round(gen_time_s, 4),
        },
        "chain_prev": (prev_receipt["receipt_id"] if prev_receipt
                       else "genesis"),
        "replay": {"status": "pending"},
    }
    body["receipt_id"] = "rcpt-" + sha256_bytes(canonical_json(body))[:16]
    return body


def receipt_hash(receipt: dict) -> str:
    """Hash of everything except receipt_id (which is derived from it)."""
    body = {k: v for k, v in receipt.items() if k != "receipt_id"}
    return "rcpt-" + sha256_bytes(canonical_json(body))[:16]


def load_log(path: str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def append_log(path: str, receipt: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False) + "\n")


def check_chain(receipts: list[dict]) -> list[str]:
    """Return integrity problems in a receipt log."""
    problems = []
    prev_id = "genesis"
    for i, r in enumerate(receipts):
        if receipt_hash(r) != r.get("receipt_id"):
            problems.append(f"[{i}] {r.get('receipt_id','?')}: content hash "
                            "does not match receipt_id (body tampered)")
        if r.get("input", {}).get("sha256") != sha256_text(
                r.get("input", {}).get("text", "")):
            problems.append(f"[{i}] {r.get('receipt_id','?')}: input hash "
                            "does not match input text")
        if r.get("output", {}).get("sha256") != sha256_text(
                r.get("output", {}).get("text", "")):
            problems.append(f"[{i}] {r.get('receipt_id','?')}: output hash "
                            "does not match output text")
        if r.get("chain_prev") != prev_id:
            problems.append(f"[{i}] {r.get('receipt_id','?')}: chain break "
                            f"(expected prev={prev_id}, got "
                            f"{r.get('chain_prev')})")
        prev_id = r.get("receipt_id", "?")
    return problems
