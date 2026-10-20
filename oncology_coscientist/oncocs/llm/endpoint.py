"""OpenAI-compatible chat endpoint backend.

The model does not have to run on the same machine as the pipeline.
Anything serving POST /v1/chat/completions works: a Colab vLLM or
Ollama instance behind a tunnel, a self-hosted llama.cpp server, or a
hosted API. Configuration is environment-only:

  ONCOCS_LLM_BASE_URL   e.g. https://xxxx.trycloudflare.com/v1
  ONCOCS_LLM_MODEL      e.g. google/gemma-3-4b-it
  ONCOCS_LLM_API_KEY    optional bearer token
  ONCOCS_LLM_TIMEOUT    seconds, default 300
  ONCOCS_LLM_MAX_TOKENS generation bound sent as max_tokens, default 1024;
                        keep under ~85s of server-side generation or a
                        Cloudflare-tunneled endpoint 502s mid-report
  ONCOCS_LLM_INTERNALS  set to 1 to request ailm internals receipts
                        (attention capture roughly halves throughput)

Requests are plain HTTP via `requests` — no SDK dependency, so the
backend works in the slim Docker image unchanged.
"""
from __future__ import annotations

import os
import time

import requests


class EndpointBackend:
    name = "endpoint"

    def __init__(self, base_url: str | None = None, model: str | None = None,
                 api_key: str | None = None,
                 timeout: float | None = None):
        self.base_url = (base_url or os.environ.get("ONCOCS_LLM_BASE_URL")
                         or "").rstrip("/")
        self.model_id = model or os.environ.get("ONCOCS_LLM_MODEL", "")
        self.api_key = api_key if api_key is not None else os.environ.get(
            "ONCOCS_LLM_API_KEY")
        self.timeout = float(
            timeout or os.environ.get("ONCOCS_LLM_TIMEOUT", "300"))
        self.max_tokens = int(
            os.environ.get("ONCOCS_LLM_MAX_TOKENS", "1024"))
        self.want_internals = os.environ.get(
            "ONCOCS_LLM_INTERNALS", "") == "1"
        if not self.base_url:
            raise ValueError(
                "endpoint backend needs ONCOCS_LLM_BASE_URL "
                "(OpenAI-compatible base, e.g. https://host/v1)")
        if not self.model_id:
            raise ValueError(
                "endpoint backend needs ONCOCS_LLM_MODEL")

    def complete(self, messages: list[dict[str, str]], *,
                 temperature: float = 0.0, seed: int | None = None) -> str:
        body: dict = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }
        if not self.want_internals:
            body["ailm_attention"] = False
        if seed is not None:
            body["seed"] = seed
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                resp = requests.post(f"{self.base_url}/chat/completions",
                                     json=body, headers=headers,
                                     timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_err = exc
            else:
                if resp.status_code == 200:
                    break
                if resp.status_code in (502, 503, 504, 429):
                    last_err = RuntimeError(
                        f"LLM endpoint {self.base_url} returned "
                        f"{resp.status_code}: {resp.text[:300]}")
                else:
                    raise RuntimeError(
                        f"LLM endpoint {self.base_url} returned "
                        f"{resp.status_code}: {resp.text[:300]}")
            time.sleep(min(5 * 2 ** attempt, 30))
        else:
            raise last_err  # type: ignore[misc]
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"malformed chat-completions response: "
                f"{str(data)[:300]}") from exc
