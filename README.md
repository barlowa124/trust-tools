# trust-tools

Tools for verifying what AI systems did — and checking whether the
watchers can be fooled. Five related projects merged into one
repository, each a self-contained package with its own tests and commit
history where applicable.

## Packages

| Directory | What it does |
|---|---|
| `agent_trajectory_audit/` | Parses coding-agent session transcripts into an event schema and flags intent/behavior divergence (unbacked test/deploy claims, abandoned plan items, out-of-scope writes, tool storms). Deterministic heuristics, zero dependencies. `trajaudit redteam` runs an adversarial battery against the detectors — attacks it evades are printed, not hidden. |
| `agent_monitor/` | The audit moved upstream: a pre-execution policy gate on tool calls. Each decision (allow/block/flag) is a hash-chained event record with severity and matched policy — for inline oversight, not post-hoc review. |
| `eval_harness/` | Task-spec evaluation runner. Deterministic graders, injectable `generate_fn`, per-task records hash-chained into a verifiable log. `sweep` runs one battery across staged checkpoints — the training-run-assessment shape. Ships `probes/abstention_battery.json` plus a real 3-stage SmolLM2 sweep under `results/`. |
| `inference_receipts/` | Hash-bound inference receipts: input, weights, settings, output all sha256-chained per log entry, with replay verification. Any tampering breaks the receipt hash or the chain. |
| `model_serve/` | Serving slice: request queue, micro-batching, shadow evaluation of a candidate against production, and a hash-bound record per response. FastAPI wiring optional. |
| `receipt_report/` | Renders audit documents from the other packages' chains — verifies integrity first, then recomputes every reported number from the records. Broken chains land in the document as findings. |

## Running tests

All six are stdlib-only. No dependencies to install:

```bash
cd agent_trajectory_audit && PYTHONPATH=src python3 -m pytest tests/ -q
cd ../agent_monitor && PYTHONPATH=src python3 -m pytest tests/ -q
cd ../eval_harness && PYTHONPATH=src python3 -m pytest tests/ -q
cd ../inference_receipts && PYTHONPATH=src python3 -m pytest tests/ -q
cd ../model_serve && PYTHONPATH=src python3 -m pytest tests/ -q
cd ../receipt_report && PYTHONPATH=src python3 -m pytest tests/ -q
cd .. && python3 -m pytest tests/ -q   # monorepo interop
```

## Why one repo

The same question at four points in a system's life: receipts prove what
a *single computation* produced; the eval harness proves what a
*checkpoint* did on a fixed battery; the monitor gates *each action
before it lands*; the audit checks whether a session's *recorded
behavior* matched stated intent — and the redteam battery measures
whether those checks can be evaded.

Every package vendors the same canonical-JSON/SHA-256 chain envelope (no
runtime dependencies between them). `tests/test_interop.py` proves the
envelopes agree: the same probe object hashes identically under all five
implementations, so a record written by one package verifies under any
other's primitives.
