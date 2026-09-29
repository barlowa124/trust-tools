"""API backend: OpenAI-compatible chat endpoints, stdlib only.

Covers OpenAI, OpenRouter, and local OpenAI-compatible servers (vLLM,
Ollama, llama.cpp) with one code path — anything that answers
POST {base}/v1/chat/completions.

The key comes from EVALH_API_KEY, then OPENAI_API_KEY. It is sent only to
the requested base URL and never written into records — the record keeps
the endpoint base + model name + settings, which is enough for a reviewer
to know what produced the output without carrying a credential.

API outputs are labeled non-replayable in the record (`replayable: false`)
— provider-side drift means the same prompt can produce a different
output tomorrow. The hash chain still binds what was actually served.
"""

from __future__ import annotations

import json
import os
import urllib.request

DEFAULT_BASE = "https://api.openai.com"


def make_generate_fn(base: str, model: str, *, max_tokens: int = 60,
                     timeout_s: float = 60.0, temperature: float = 0.0):
    """Return a generate_fn(prompt)->str hitting an OpenAI-compatible API."""
    key = os.environ.get("EVALH_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit(
            "set EVALH_API_KEY (or OPENAI_API_KEY) for the API backend")
    url = base.rstrip("/") + "/v1/chat/completions"

    def gen(prompt: str) -> str:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {key}"},
            method="POST")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"] or ""

    return gen


def model_meta(base: str, model: str) -> dict:
    """Record identity for API runs: endpoint + model name, replayable
    flag honest about provider-side nondeterminism."""
    return {"name": model, "api_base": base, "replayable": False}
