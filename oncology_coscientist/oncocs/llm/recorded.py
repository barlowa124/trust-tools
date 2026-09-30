"""Recording and replaying backends."""
from __future__ import annotations

import hashlib
import json
import time


def _prompt_sha(messages: list[dict[str, str]]) -> str:
    canon = json.dumps(messages, sort_keys=True).encode()
    return hashlib.sha256(canon).hexdigest()


class RecordingBackend:
    """Wraps any backend; appends each call to an in-memory transcript."""

    def __init__(self, inner):
        self.inner = inner
        self.name = inner.name
        self.model_id = inner.model_id
        self.transcript: list[dict] = []

    def complete(self, messages: list[dict[str, str]], *,
                 temperature: float = 0.0, seed: int | None = None) -> str:
        t0 = time.monotonic()
        resp = self.inner.complete(messages, temperature=temperature, seed=seed)
        self.transcript.append({
            "index": len(self.transcript),
            "prompt_sha256": _prompt_sha(messages),
            "messages": messages,
            "response": resp,
            "backend": self.inner.name,
            "model_id": self.inner.model_id,
            "temperature": temperature,
            "seed": seed,
            "elapsed_s": round(time.monotonic() - t0, 3),
        })
        return resp


class TranscriptMismatch(Exception):
    pass


class RecordedBackend:
    """Replays a transcript by index; verifies the issued prompt matches."""

    name = "recorded"

    def __init__(self, transcript: list[dict]):
        self.transcript = transcript
        self.model_id = transcript[0]["model_id"] if transcript else "recorded"
        self._i = 0

    def complete(self, messages: list[dict[str, str]], *,
                 temperature: float = 0.0, seed: int | None = None) -> str:
        if self._i >= len(self.transcript):
            raise TranscriptMismatch(
                f"Replay exhausted: call {self._i} but transcript has {len(self.transcript)}")
        entry = self.transcript[self._i]
        self._i += 1
        actual = _prompt_sha(messages)
        if actual != entry["prompt_sha256"]:
            raise TranscriptMismatch(
                f"Prompt mismatch at index {entry['index']}: "
                f"recorded {entry['prompt_sha256'][:12]} != issued {actual[:12]}")
        return entry["response"]


class ScriptedBackend:
    """Fixed responses for tests."""

    name = "scripted"
    model_id = "scripted-demo"

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self._i = 0

    def complete(self, messages: list[dict[str, str]], *,
                 temperature: float = 0.0, seed: int | None = None) -> str:
        resp = self.responses[min(self._i, len(self.responses) - 1)]
        self._i += 1
        return resp
