# SmolLM2 post-training checkpoint assessment

Generated 2026-09-29T16:03:31.480007+00:00 from hash-chained records. Every figure below is recomputed from the committed logs; chain integrity was checked per log at build time.

*chain verified: 32 records, kind=eval_result*

## Evaluation run — sft.jsonl

**Model**: `sft` — weights model.safetensors=c3798bfa3793…
**Spec**: sha256 `4e4e23baffc9fa4b…`
**Tasks**: 32 across tags: answerable, format, unanswerable

| tag | score | labels |
|---|---|---|
| answerable | 0.27 | degenerate:11 pass:4 |
| format | 0.00 | degenerate:2 |
| unanswerable | 1.00 | abstains:15 |

Overall label counts: abstains=15, degenerate=13, pass=4

*chain verified: 32 records, kind=eval_result*

## Evaluation run — dpo.jsonl

**Model**: `dpo` — weights model.safetensors=6f2fd81f0eef…
**Spec**: sha256 `4e4e23baffc9fa4b…`
**Tasks**: 32 across tags: answerable, format, unanswerable

| tag | score | labels |
|---|---|---|
| answerable | 0.00 | degenerate:14 fail:1 |
| format | 0.00 | degenerate:2 |
| unanswerable | 0.13 | abstains:2 degenerate:13 |

Overall label counts: abstains=2, degenerate=29, fail=1

*chain verified: 32 records, kind=eval_result*

## Evaluation run — grpo.jsonl

**Model**: `grpo` — weights model.safetensors=66d4023f70eb…
**Spec**: sha256 `4e4e23baffc9fa4b…`
**Tasks**: 32 across tags: answerable, format, unanswerable

| tag | score | labels |
|---|---|---|
| answerable | 0.00 | degenerate:15 |
| format | 0.00 | degenerate:2 |
| unanswerable | 1.00 | abstains:15 |

Overall label counts: abstains=15, degenerate=17

## Integrity summary

All chains verified.

## Limits

- This report covers only the recorded runs; it is not a capability or safety claim about the model family.
- Chain verification proves the logs are unmodified since creation, not that the underlying evaluations were correct.
- Replay (re-running generation to compare outputs) is a stronger check and is reported separately where available.
