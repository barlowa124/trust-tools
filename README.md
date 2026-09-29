# trust-tools

Tools for verifying what AI systems did. Two related projects
merged into one repository, each a self-contained package with its own
tests and commit history (imported via subtree merge).

## Packages

| Directory | What it does |
|---|---|
| `agent_trajectory_audit/` | Parses coding-agent session transcripts into an event schema and flags intent/behavior divergence (unbacked test/deploy claims, abandoned plan items, out-of-scope writes, tool storms). Deterministic heuristics, zero dependencies. |
| `inference_receipts/` | Hash-bound inference receipts: input, weights, settings, output all sha256-chained per log entry, with replay verification. Any tampering breaks the receipt hash or the chain. |

## Running tests

Both are stdlib-only. No dependencies to install:

```bash
cd agent_trajectory_audit && PYTHONPATH=src python3 -m pytest tests/ -q
cd inference_receipts && PYTHONPATH=src python3 -m pytest tests/ -q
```

## Why one repo

Same question at two levels: trajectory audit checks whether the agent's
*recorded behavior* matched its stated intent. Receipts prove what a
*single computation* produced. The first cross-package piece is live.
`trajaudit attest` emits each audit finding as a hash-chained record using
the same canonical-JSON envelope as `llmreceipt` (vendored, not depended
on, so trajaudit stays stdlib-only). `tests/test_interop.py` at the repo
root verifies emitted logs using llmreceipt's own hash primitives, so
format drift between the packages fails loudly.
