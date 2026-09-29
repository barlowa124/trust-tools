"""Verify receipts: hash integrity, chain, and live replay.

Integrity checks are pure hash recomputation and work anywhere. Replay
re-runs the generation under the recorded backend and compares the output
hash; it is meaningful only when the recorded backend is reproduced
(same transformers/torch, CPU, float32). A replay on different hardware or
library versions is a characterization result, not a verdict: report it as
'mismatch' only with the caveat attached.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from .capture import _snapshot_dir
from .receipt import (check_chain, receipt_hash, sha256_text)


def check_integrity(receipt: dict) -> list[str]:
    problems = []
    if receipt_hash(receipt) != receipt.get("receipt_id"):
        problems.append("receipt_id does not match content hash "
                        "(body tampered or truncated)")
    for part in ("input", "output"):
        blk = receipt.get(part, {})
        if blk.get("sha256") != sha256_text(blk.get("text", "")):
            problems.append(f"{part}.sha256 does not match {part}.text")
    return problems


def replay_hf(receipt: dict) -> dict:
    """Re-run the recorded generation and compare output hashes.

    Returns a replay block to store on the receipt. Never mutates the
    recorded output; comparison is hash-vs-hash.
    """
    import torch
    import transformers

    model = receipt["model"]
    gen = receipt["generation"]
    model_dir = _snapshot_dir(model["id"], model.get("revision"))
    tok = transformers.AutoTokenizer.from_pretrained(model_dir)
    m = transformers.AutoModelForCausalLM.from_pretrained(
        model_dir, dtype=torch.float32)
    m.eval()
    ids = tok(receipt["input"]["text"], return_tensors="pt").input_ids
    t0 = time.perf_counter()
    with torch.no_grad():
        out = m.generate(ids, do_sample=bool(gen.get("do_sample", False)),
                         temperature=gen.get("temperature") or None,
                         max_new_tokens=int(gen["max_new_tokens"]),
                         pad_token_id=tok.eos_token_id)
    dt = time.perf_counter() - t0
    new_text = tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True)
    match = sha256_text(new_text) == receipt["output"]["sha256"]
    return {
        "status": "verified" if match else "mismatch",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "replay_backend": {"kind": "hf-transformers",
                           "transformers": transformers.__version__,
                           "torch": torch.__version__},
        "output_sha256_on_replay": sha256_text(new_text),
        "replay_gen_time_s": round(dt, 4),
    }


def verify_log(receipts: list[dict], replay: bool = False) -> dict:
    problems = check_chain(receipts)
    per_receipt = {}
    replay_results = {}
    for r in receipts:
        rid = r.get("receipt_id", "?")
        ps = check_integrity(r)
        if replay and not ps:
            # replay outcome is verification metadata: it must not be written
            # into the receipt, because receipt_id binds the recorded body
            # (including the original replay={status: pending} block)
            rb = replay_hf(r)
            replay_results[rid] = rb
            if rb["status"] == "mismatch":
                ps.append("replay output hash differs from recorded output")
        per_receipt[rid] = ps
        problems.extend(f"{rid}: {p}" for p in ps)
    return {"ok": not problems, "n_receipts": len(receipts),
            "problems": problems, "per_receipt": per_receipt,
            "replay": replay_results}
