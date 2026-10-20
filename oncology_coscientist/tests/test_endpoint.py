"""EndpointBackend: request shape, error paths, env configuration.
No network — requests.post is stubbed."""
from __future__ import annotations

import pytest

from oncocs.llm.endpoint import EndpointBackend


class _Resp:
    def __init__(self, status=200, data=None, text=""):
        self.status_code = status
        self._data = data or {}
        self.text = text

    def json(self):
        return self._data


def test_env_configuration(monkeypatch):
    monkeypatch.setenv("ONCOCS_LLM_BASE_URL", "https://x.trycloudflare.com/v1/")
    monkeypatch.setenv("ONCOCS_LLM_MODEL", "gemma-3-4b")
    b = EndpointBackend()
    assert b.base_url == "https://x.trycloudflare.com/v1"
    assert b.model_id == "gemma-3-4b"


def test_missing_config_raises(monkeypatch):
    monkeypatch.delenv("ONCOCS_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("ONCOCS_LLM_MODEL", raising=False)
    with pytest.raises(ValueError):
        EndpointBackend()
    with pytest.raises(ValueError):
        EndpointBackend(base_url="http://x/v1")


def test_request_shape(monkeypatch):
    calls = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.update(url=url, json=json, headers=headers, timeout=timeout)
        return _Resp(200, {"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr("requests.post", fake_post)
    b = EndpointBackend(base_url="http://colab/v1", model="m",
                        api_key="k")
    out = b.complete([{"role": "user", "content": "hi"}],
                     temperature=0.0, seed=7)
    assert out == "ok"
    assert calls["url"] == "http://colab/v1/chat/completions"
    assert calls["json"]["model"] == "m"
    assert calls["json"]["seed"] == 7
    assert calls["headers"]["Authorization"] == "Bearer k"


def test_generation_bounds_in_request(monkeypatch):
    """max_tokens bounds the generation; ailm_attention stays off so the
    receipt's per-step attention capture doesn't halve throughput."""
    calls = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.update(json=json)
        return _Resp(200, {"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.delenv("ONCOCS_LLM_MAX_TOKENS", raising=False)
    b = EndpointBackend(base_url="http://colab/v1", model="m")
    b.complete([{"role": "user", "content": "hi"}], temperature=0.0)
    assert calls["json"]["max_tokens"] == 1024
    assert calls["json"]["ailm_attention"] is False

    monkeypatch.setenv("ONCOCS_LLM_MAX_TOKENS", "512")
    monkeypatch.setenv("ONCOCS_LLM_INTERNALS", "1")
    b = EndpointBackend(base_url="http://colab/v1", model="m")
    b.complete([{"role": "user", "content": "hi"}], temperature=0.0)
    assert calls["json"]["max_tokens"] == 512
    assert "ailm_attention" not in calls["json"]


def test_error_status_and_malformed(monkeypatch):
    monkeypatch.setattr("requests.post",
                        lambda *a, **k: _Resp(502, text="bad gateway"))
    b = EndpointBackend(base_url="http://x/v1", model="m")
    with pytest.raises(RuntimeError, match="502"):
        b.complete([{"role": "user", "content": "hi"}])
    monkeypatch.setattr("requests.post",
                        lambda *a, **k: _Resp(200, {"choices": []}))
    with pytest.raises(RuntimeError, match="malformed"):
        b.complete([{"role": "user", "content": "hi"}])
