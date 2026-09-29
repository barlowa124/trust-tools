"""modelserve: a small model-serving slice with receipts.

Serving mechanics a platform team actually runs — request queueing,
micro-batching, shadow comparison of a candidate model against the
production model — bound to hash-chained response receipts so "what the
deployment served" is replayable evidence.

The core is dependency-free: `generate_fn` is injectable, so tests run
offline. `app.py` wires the same service behind FastAPI when installed.
"""
