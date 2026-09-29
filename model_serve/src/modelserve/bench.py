"""Serving benchmark: concurrent load -> latency/throughput report.

Drives a Service with `concurrency` client threads over `n_requests`
prompts and reports client-side wall latency plus the record's own
queued_s / latency_s, as percentiles. The committed artifact is a real
measurement on a small CPU checkpoint — honest scale, not a datacenter
claim.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from .service import Service


def pct(values: list[float], q: float) -> float:
    """Linear-interpolated percentile; q in [0, 100]."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (q / 100)
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _summ(values: list[float]) -> dict:
    return {"p50": round(pct(values, 50), 4),
            "p90": round(pct(values, 90), 4),
            "p95": round(pct(values, 95), 4),
            "p99": round(pct(values, 99), 4),
            "mean": round(sum(values) / len(values), 4) if values else 0,
            "max": round(max(values), 4) if values else 0}


def run_bench(generate_fn: Callable[[str], str], model: dict,
              *, n_requests: int = 100, concurrency: int = 8,
              batch_size: int = 8, batch_window_s: float = 0.050,
              prompt: str | Callable[[int], str] | None = None,
              seed: int = 0) -> dict:
    """Fire n_requests through concurrency clients; return the report."""
    svc = Service(generate_fn, model, batch_size=batch_size,
                  batch_window_s=batch_window_s, seed=seed)
    svc.start()
    wall_lat, errors = [], []
    it = iter(range(n_requests))
    lock = threading.Lock()

    def client():
        while True:
            with lock:
                i = next(it, None)
            if i is None:
                return
            p = prompt(i) if callable(prompt) else \
                (prompt or f"benchmark request {i}")
            t0 = time.perf_counter()
            try:
                svc.infer(p)
            except Exception as e:          # timeouts count, not crash
                errors.append(str(e))
            wall_lat.append(time.perf_counter() - t0)

    t0 = time.perf_counter()
    threads = [threading.Thread(target=client)
               for _ in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t0
    svc.stop()

    recs = svc.records
    return {
        "config": {"n_requests": n_requests, "concurrency": concurrency,
                   "batch_size": batch_size,
                   "batch_window_s": batch_window_s},
        "n_served": len(recs), "n_errors": len(errors),
        "errors": errors[:5],
        "wall_s": round(wall, 3),
        "throughput_rps": round(len(recs) / wall, 2) if wall else 0,
        "batches": svc.stats["batches"],
        "client_latency_s": _summ(wall_lat),
        "queued_s": _summ([r["queued_s"] for r in recs]),
        "gen_s": _summ([r["latency_s"] for r in recs]),
        "chain_problems": svc.check_chain(),
    }


def sweep(generate_fn: Callable[[str], str], model: dict,
          batch_sizes: list[int], **kw) -> list[dict]:
    """One run_bench per batch size — the axis that trades latency for
    throughput."""
    return [run_bench(generate_fn, model, batch_size=b, **kw)
            for b in batch_sizes]


def table(reports: list[dict]) -> str:
    head = (f"{'batch':>5} {'conc':>4} {'rps':>8} {'p50 ms':>9} "
            f"{'p95 ms':>9} {'p99 ms':>9} {'q p95 ms':>9} {'batches':>8}")
    rows = [head]
    for r in reports:
        c = r["config"]
        rows.append(
            f"{c['batch_size']:>5} {c['concurrency']:>4} "
            f"{r['throughput_rps']:>8} "
            f"{r['client_latency_s']['p50'] * 1000:>9.1f} "
            f"{r['client_latency_s']['p95'] * 1000:>9.1f} "
            f"{r['client_latency_s']['p99'] * 1000:>9.1f} "
            f"{r['queued_s']['p95'] * 1000:>9.1f} "
            f"{r['batches']:>8}")
    return "\n".join(rows)
