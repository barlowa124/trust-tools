# agentob

Agent trace ingestion, live-policy enrichment, and trace reporting.
`agentmon` gates calls before execution and `trajaudit` audits
transcripts after the fact. `agentob` ingests the span trace that
observability stacks already produce.

```bash
agentob report trace.json --html report.html
agentob report trace.json --events events.jsonl --alerts alerts.jsonl
```

## What it does

1. **Ingest**: flat span JSON (`span_id`, `parent_id`, `name`, `kind`,
   `start_ms`, `end_ms`, `attrs`) or a minimal OTLP/JSON export
   (`resourceSpans[].scopeSpans[].spans[]`, common fields only, not the
   full spec). Duplicate ids, orphan parents, and negative durations
   are rejected.
2. **Enrich**: every `tool_call` span is evaluated against the
   `agentmon` policy (`evaluate`, non-raising), so the verdict lands on
   the span. Flagged and denied spans are also written into a Monitor's
   hash-chained alert log, which `receipt_report` already renders.
3. **Audit**: spans convert to trajaudit-schema events and run the
   detector suite, so gate verdicts and post-hoc findings share one
   stream.
4. **Render**: markdown or self-contained HTML. Indented span tree,
   duration bars, per-span verdict, findings section.

Sibling packages are soft dependencies. Without `agentmon`/`trajaudit`
importable the report still renders and says which layers were skipped.

## Example

`examples/agent_run.json` is a 9-span run containing one in-scope write,
three denied calls (pipe-to-shell, sudo, `.env` read), one flagged
network fetch, and an unbacked "all tests pass" claim. The committed
`examples/report.md` shows the full rendered output. The denied spans
carry their rule ids and `verification_claim_gap` fires on the claim.

## Limits

- The OTLP mapper covers the common export fields. OTLP events, links,
  and resource attributes are outside that set and get dropped.
- No tail-sampling or streaming ingest. This reads a finished export.
- Verdicts evaluate string arguments only and inherit agentmon's
  documented residual (symlink escapes), because span attrs cannot see
  the filesystem.
- The demo trace is synthetic. It exercises the pipeline, and it is not
  evidence about any real agent.

## Tests

```bash
PYTHONPATH=src python -m pytest tests/ -q    # 12 tests
```

Tests add the sibling `src/` dirs to `sys.path`. agentmon and trajaudit
behaviors are exercised for real, not mocked.
