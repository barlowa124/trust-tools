"""Hugging Face backend for modelserve. Optional: `pip install .[hf]`."""

from __future__ import annotations


def make_generate_fn(model_dir: str, max_new_tokens: int = 60):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_dir)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_dir, dtype=torch.float32)
    model.eval()

    def gen(prompt: str) -> str:
        ids = tok(prompt, return_tensors="pt").input_ids
        with torch.no_grad():
            out = model.generate(
                ids, max_new_tokens=max_new_tokens, do_sample=False,
                pad_token_id=tok.pad_token_id)
        return tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True)

    return gen


def model_meta(model_dir: str) -> dict:
    """Dir basename + weights hashes. No absolute path — records commit."""
    import hashlib
    from pathlib import Path
    d = Path(model_dir)
    weights = {}
    for p in sorted(d.iterdir()):
        if p.suffix in (".safetensors", ".bin", ".pt"):
            h = hashlib.sha256()
            with open(p, "rb") as f:
                while True:
                    b = f.read(1 << 20)
                    if not b:
                        break
                    h.update(b)
            weights[p.name] = h.hexdigest()
    return {"name": d.name, "weights_sha256": weights}
