# receipt_report

Markdown audit documents generated from hash-chained record logs.

Reads the JSONL logs produced by the sibling trust-tools packages —
evalh `eval_result` runs, modelserve `serve_response` chains, llmreceipt
inference receipts — verifies each chain, then renders one section per
log: model identity, task coverage, label distribution, latency and
shadow-agreement stats. Every number is recomputed from the records at
build time.

A broken chain is reported as a finding in the document, not filtered.
The generated limits section states what the evidence cannot support:
chain verification proves logs are unmodified since creation, not that
the underlying evaluations were correct — replay is the stronger check.

```
rcptreport build run1.jsonl serve.jsonl --title "Assessment" --out report.md
```
