# traj_review_ui

Static React + TypeScript review UI for agent trajectories and the audit
findings produced by `agent_trajectory_audit`.

## Overview

A reviewer-facing surface for the repo's real artifact formats. It loads
committed JSONL trajectories (the `trajaudit audit` input format) plus
their audit reports, and renders

- a stats bar with session id, per-kind event counts, finding count, and
  time span
- a findings panel with severity, detector name, summary, evidence, and a
  jump-to-event link per finding
- an event timeline with kind badges, tool names, expandable event
  bodies, tool_call to tool_result pairing via `call_id`, rows flagged
  where a finding points, kind filters, and text search
- a span-tree view for `agent_observe` traces: parent-linked spans with
  per-span duration bars, covering the second artifact family in the repo

## Honest scope

This is a **static demo**. The four bundled datasets are real artifacts
from `agent_trajectory_audit/examples/` (one clean run, three with
detector findings), imported as raw text at build time. There is no live
backend. Wiring a `fetch` against the audit CLI's report output is the
obvious next step but is not implemented.

## Run

```bash
npm install
npm run dev        # local preview
npm test           # 12 vitest tests: parser, pairing, UI behavior
npm run build      # tsc typecheck + vite bundle
```

## Layout

- `src/parse.ts`: JSONL/report parsing, call_id pairing, findings index.
  Pure functions, fully tested without a DOM.
- `src/components/`: StatsBar, FindingsPanel, Timeline, EventRow,
  SpanTree.
- `src/sample/`: bundled trajectory + report pairs (copies of
  `agent_trajectory_audit/examples/`) plus the `agent_observe` example
  span trace.
