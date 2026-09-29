"""Serving service: queue -> micro-batch -> response -> receipt.

The service owns a primary generate_fn and an optional shadow candidate.
Every request gets a response record: input/output hashes, latency, batch
membership, model identity, and a chain link to the previous record — the
same envelope as inference_receipts and evalh so logs interoperate.

Shadow mode runs the candidate on a configurable fraction of traffic and
records agreement between primary and shadow outputs. Shadow divergence
is data, not an error — it lands in the record and the shadow report.
"""

from __future__ import annotations

import hashlib
import json
import random
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable

SCHEMA_VERSION = 1


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


class Service:
    """Queued inference over an injectable generate_fn.

    Parameters
    ----------
    generate_fn : prompt -> text, the production model.
    model : identity dict for the production model.
    shadow_fn / shadow_model : optional candidate served on
        `shadow_fraction` of requests for comparison.
    batch_size / batch_window_s : micro-batching knobs — requests collect
        until the batch is full or the window expires.
    """

    def __init__(self, generate_fn: Callable[[str], str], model: dict,
                 *, shadow_fn: Callable[[str], str] | None = None,
                 shadow_model: dict | None = None,
                 shadow_fraction: float = 0.0,
                 batch_size: int = 8, batch_window_s: float = 0.050,
                 seed: int = 0):
        self.generate_fn = generate_fn
        self.model = model
        self.shadow_fn = shadow_fn
        self.shadow_model = shadow_model or {}
        self.shadow_fraction = shadow_fraction
        self.batch_size = batch_size
        self.batch_window_s = batch_window_s
        self._rng = random.Random(seed)
        self._queue: deque = deque()
        self._lock = threading.Condition()
        self._records: list[dict] = []
        self._prev_id = "genesis"
        self._stop = False
        self._worker: threading.Thread | None = None
        self.stats = {"requests": 0, "batches": 0, "shadow_runs": 0,
                      "shadow_agree": 0, "shadow_diverge": 0}

    # -- lifecycle -------------------------------------------------------

    def start(self):
        self._worker = threading.Thread(target=self._drain, daemon=True)
        self._worker.start()

    def stop(self, drain: bool = True):
        self._stop = True
        with self._lock:
            self._lock.notify_all()
        if self._worker:
            self._worker.join(timeout=5)
        if drain:
            while self._queue:
                self._serve_batch()

    # -- public API ------------------------------------------------------

    def infer(self, prompt: str, timeout_s: float = 30.0) -> dict:
        """Enqueue a prompt; block until its response record exists."""
        fut: dict[str, Any] = {}
        ev = threading.Event()
        with self._lock:
            self._queue.append({"prompt": prompt, "fut": fut, "ev": ev,
                                "enqueued_at": time.perf_counter()})
            self._lock.notify_all()
        if not ev.wait(timeout_s):
            raise TimeoutError("inference timed out")
        return fut["record"]

    @property
    def records(self) -> list[dict]:
        return list(self._records)

    # -- internals -------------------------------------------------------

    def _drain(self):
        while not self._stop:
            with self._lock:
                self._lock.wait_for(
                    lambda: self._queue or self._stop,
                    timeout=self.batch_window_s)
            if self._queue:
                self._serve_batch()

    def _serve_batch(self):
        with self._lock:
            batch = []
            while self._queue and len(batch) < self.batch_size:
                batch.append(self._queue.popleft())
        if not batch:
            return
        self.stats["batches"] += 1
        for req in batch:
            self._serve_one(req)

    def _serve_one(self, req: dict):
        t0 = time.perf_counter()
        out = self.generate_fn(req["prompt"])
        dt = time.perf_counter() - t0
        queued_s = t0 - req["enqueued_at"]

        shadow = None
        if (self.shadow_fn is not None
                and self._rng.random() < self.shadow_fraction):
            s_out = self.shadow_fn(req["prompt"])
            agree = s_out == out
            self.stats["shadow_runs"] += 1
            self.stats["shadow_agree" if agree else "shadow_diverge"] += 1
            shadow = {"model": self.shadow_model,
                      "output_sha256": sha256_text(s_out),
                      "output": s_out,
                      "agrees_with_primary": agree}

        self.stats["requests"] += 1
        body = {
            "v": SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "kind": "serve_response",
            "model": self.model,
            "input": {"text": req["prompt"],
                      "sha256": sha256_text(req["prompt"])},
            "output": {"text": out, "sha256": sha256_text(out)},
            "latency_s": round(dt, 4),
            "queued_s": round(queued_s, 4),
            "shadow": shadow,
            "chain_prev": self._prev_id,
        }
        body["response_id"] = "srv-" + sha256_bytes(
            canonical_json(body))[:16]
        self._records.append(body)
        self._prev_id = body["response_id"]
        req["fut"]["record"] = body
        req["ev"].set()

    # -- verification ----------------------------------------------------

    def check_chain(self) -> list[str]:
        problems, prev = [], "genesis"
        for i, r in enumerate(self._records):
            body = {k: v for k, v in r.items() if k != "response_id"}
            rid = "srv-" + sha256_bytes(canonical_json(body))[:16]
            if rid != r["response_id"]:
                problems.append(f"[{i}] content hash mismatch")
            if r["chain_prev"] != prev:
                problems.append(f"[{i}] chain break")
            if sha256_text(r["input"]["text"]) != r["input"]["sha256"]:
                problems.append(f"[{i}] input hash mismatch")
            if sha256_text(r["output"]["text"]) != r["output"]["sha256"]:
                problems.append(f"[{i}] output hash mismatch")
            prev = r["response_id"]
        return problems

    def report(self) -> dict:
        """Serving report: throughput stats + shadow agreement rate."""
        reps = self._records
        lat = [r["latency_s"] for r in reps] or [0.0]
        q = [r["queued_s"] for r in reps] or [0.0]
        sh = self.stats["shadow_runs"]
        return {
            "requests": self.stats["requests"],
            "batches": self.stats["batches"],
            "mean_latency_s": sum(lat) / len(lat),
            "max_latency_s": max(lat),
            "mean_queued_s": sum(q) / len(q),
            "shadow": None if not sh else {
                "runs": sh,
                "fraction": self.shadow_fraction,
                "agree_rate": self.stats["shadow_agree"] / sh,
                "diverged": self.stats["shadow_diverge"],
                "candidate": self.shadow_model,
            },
        }
