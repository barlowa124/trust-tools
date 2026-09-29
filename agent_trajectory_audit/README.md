# agent-trajectory-audit

Audit coding-agent sessions for divergence between stated intent and
observed behavior. `trajaudit` ingests agent transcripts, normalizes them
to an event stream, and runs deterministic detectors that flag where what
the agent *did* departs from what it *said it was doing*: claims of passing
tests with no test run, completed verification todos with no verification
command, plans that silently grew or dropped items, writes outside the
session's working territory, and long stretches of unplanned tool use.

This is oversight applied to a real subject. The committed example is a
sanitized window of a Devin CLI session building a dashboard app in
[cultivated-meat-multiomic](../cultivated-meat-multiomic). The detectors
run on the agent's own working sessions, not a synthetic benchmark.

## Why this exists

Agent evals mostly score outputs. The oversight question is narrower:
inside a session, do the agent's actions match its stated plan, and do its
claims match the evidence in its own tool history? A human reviewer cannot
read 15k events. They can read a list of 16 findings that each point at
specific events to inspect.

Findings are pointers, not verdicts. Every finding carries `event_i`
indices into the trajectory for human review, and the report states the
heuristic's known false-positive modes.

## Usage

```bash
pip install -e .

# List sessions in a Devin CLI transcript database
trajaudit sessions --db ~/.local/share/devin/cli/sessions.db

# Extract one session (or a window) to normalized events
trajaudit ingest-devin --db ~/.local/share/devin/cli/sessions.db \
    --session <id> --out trajectory.jsonl [--sanitize] [--window A:B]

# Redact an existing trajectory before sharing it
trajaudit sanitize trajectory.jsonl --out clean.jsonl

# Run the detectors
trajaudit audit trajectory.jsonl                 # markdown to stdout
trajaudit audit trajectory.jsonl --md report.md --json report.json
```

Python 3.10+, standard library only for ingest/audit. pytest for tests.

## Event schema

One JSON object per line:

| Field | Meaning |
|---|---|
| `i` | Event position in the trajectory |
| `kind` | `user`, `assistant`, `thinking`, `plan`, `tool_call`, `tool_result` |
| `t` | Epoch seconds when known |
| `text` | Message text or tool result body |
| `tool` | Tool name (`exec`, `edit`, `read`, ...) |
| `call_id` | Links a `tool_call` to its `tool_result` |
| `plan` | On `plan` events: `[{content, status}]` snapshot |
| `args` | Selected tool args (`command`, `file_path`, `query`, ...) |

`todo_write`-style calls become `plan` events, which is where stated intent
comes from. Other transcript formats can be normalized to this schema. The
detectors only read the JSONL.

## Detectors

| Detector | Flags | Known false positives |
|---|---|---|
| `verification_claim_gap` | Assistant claims (tests pass, verified live, deployed) with no matching command anywhere earlier in the trajectory | Claims summarizing pre-window work; claims about things other than the agent's own run |
| `completion_without_verification` | A verify/test/deploy todo flips to completed with no verification command between activation and completion | Verification done by hand or through a tool the command regex misses |
| `abandoned_items` | Plan items dropped from later snapshots or still pending at the end | Intentionally deferred work |
| `plan_drift` | Pending items added mid-run that are not refinements (fuzzy-matched) of earlier items | Legitimate reactive replanning |
| `scope_drift` | Writes (`edit`/`write`/`notebook_edit`, exec redirects/git/cp/mv/mkdir) outside the path territory the session established | Conventional scratch dirs like `/tmp`; territory expansion is allowed gradually, jumps are flagged |
| `unplanned_work` | Sessions with >=20 tool calls and no plan events | Sessions where planning lives outside the transcript |

The command-matching regexes live in `detectors.py` (`VERIFY_CMD`,
`CLAIMS`, `_WRITEISH_CMD`) and are deliberately small and readable so a
reviewer can audit what counts as evidence.

## Committed examples

- `examples/trajectories/dashboard-build-window.jsonl`: a 476-event
  sanitized window of a real Devin session building a standalone dashboard
  app. `examples/reports/dashboard-build-window.{md,json}` is its audit:
  2 findings, one of which (`unverified_claims`-style claim referencing
  work before the window) is a documented false-positive mode, not
  a real failure. That is the intended reading. The finding is correct
  that no evidence exists *inside the trajectory*. The human checks and
  moves on.
- `examples/fixtures/`: small hand-written trajectories exercising each
  detector (`clean_run`, `unverified_claims`, `drift_and_scope`).

## Sanitization

`sanitize` rewrites paths under `$HOME`, emails, token-looking strings,
and non-loopback IPv4 literals, and drops `thinking` events entirely
(reasoning text tends to quote private context verbatim). It does not try
to detect names or employer identifiers in prose. Review sanitized output
before publishing. Redaction is a pipeline step, not a guarantee.

## Limits

- Heuristics, not judgments. The detectors answer "is there an event to
  look at", not "did the agent misbehave".
- Evidence commands are matched by regex. Verification performed through
  an API call, a GUI, or a previous session will not count.
- `unplanned_work` sees only this transcript. If the agent's planner is a
  different subsystem, the finding is about missing observability, which
  is itself worth recording.
- Currently ingests Devin CLI `sessions.db`. Other formats join through
  the documented JSONL schema.

## Development

```bash
python -m pytest tests/ -q     # 27 tests
```

MIT license.
