"""Hugging Face backend: load a local checkpoint dir, greedy generation.

Optional dependency — `pip install -e .[hf]`. The rest of the package is
stdlib-only.
"""

from __future__ import annotations


def make_generate_fn(model_dir: str, max_new_tokens: int = 60):
    """Return a generate_fn(prompt)->str for a local HF model dir."""
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
    """Model identity for run records: dir basename + per-file weights
    hashes. No absolute path — logs get committed, and the weights hash is
    the actual identity anyway."""
    from .chainfmt import sha256_file
    from pathlib import Path
    d = Path(model_dir)
    weight_files = sorted(
        p for p in d.iterdir()
        if p.suffix in (".safetensors", ".bin", ".pt"))
    return {
        "name": d.name,
        "weights_sha256": {
            p.name: sha256_file(str(p)) for p in weight_files
        },
    }
