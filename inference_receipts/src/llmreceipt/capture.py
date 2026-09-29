"""Capture: run an LLM call and produce a receipt.

Only the HF transformers path is implemented; it is the backend where
greedy CPU generation is deterministic, which is what makes replay
verification meaningful. The weights hash binds the receipt to the exact
parameter files (all safetensors/bin shards in the snapshot, hashed
together in sorted order), not just a model id.
"""

from __future__ import annotations

import glob
import os
import time

from .receipt import make_receipt, sha256_file

WEIGHT_GLOBS = ("*.safetensors", "*.bin")


def _weights_sha256(model_dir: str) -> str:
    import hashlib
    h = hashlib.sha256()
    files = sorted(p for g in WEIGHT_GLOBS
                   for p in glob.glob(os.path.join(model_dir, g)))
    for p in files:
        h.update(os.path.basename(p).encode())
        h.update(sha256_file(p).encode())
    return h.hexdigest()


def _snapshot_dir(model_id: str, revision: str | None) -> str:
    from huggingface_hub import snapshot_download
    return snapshot_download(model_id, revision=revision,
                             allow_patterns=["*.safetensors", "*.bin",
                                             "*.json", "*.model",
                                             "tokenizer*"])


def capture_hf(model_id: str, prompt: str, *, max_new_tokens: int = 64,
               revision: str | None = None,
               prev_receipt: dict | None = None) -> dict:
    import torch
    import transformers

    model_dir = _snapshot_dir(model_id, revision)
    tok = transformers.AutoTokenizer.from_pretrained(model_dir)
    model = transformers.AutoModelForCausalLM.from_pretrained(
        model_dir, dtype=torch.float32)
    model.eval()

    revision_resolved = getattr(model.config, "_commit_hash", None) or revision
    ids = tok(prompt, return_tensors="pt").input_ids
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model.generate(ids, do_sample=False, max_new_tokens=max_new_tokens,
                             pad_token_id=tok.eos_token_id)
    dt = time.perf_counter() - t0
    new_ids = out[0][ids.shape[1]:]
    text = tok.decode(new_ids, skip_special_tokens=True)

    backend = {"kind": "hf-transformers",
               "transformers": transformers.__version__,
               "torch": torch.__version__, "device": "cpu",
               "dtype": "float32"}
    model_info = {"id": model_id, "revision": revision_resolved,
                  "weights_sha256": _weights_sha256(model_dir)}
    generation = {"do_sample": False, "temperature": 0.0,
                  "max_new_tokens": max_new_tokens}
    return make_receipt(backend=backend, model=model_info,
                        input_text=prompt, generation=generation,
                        output_text=text, gen_time_s=dt,
                        n_new_tokens=int(new_ids.numel()),
                        prev_receipt=prev_receipt)
