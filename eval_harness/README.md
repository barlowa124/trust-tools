# eval_harness

Task-spec evaluation runner with hash-chained, verifiable result logs.

An eval is a JSON task spec (prompt, grader, tag). The runner feeds each
prompt through an injectable `generate_fn` — the core is stdlib-only —
and emits one record per task: task id, output text + hash, grade label,
latency, model identity, and `chain_prev` linking to the prior record.
Editing, reordering, or dropping a record breaks the chain check.

```
evalh run --tasks spec.json --model-dir CKPT --out run.jsonl
evalh sweep --tasks spec.json --model-dirs sft=D1,dpo=D2 --out-dir out/
evalh verify run.jsonl
evalh report sweep_summary.json --md report.md
```

Graders are deterministic: `exact`, `contains`, `not_contains`,
`regex`, `abstain`. Degenerate outputs (repetition collapse) are labeled
`degenerate` and score zero regardless of keyword match — an echo loop
that incidentally contains the gold token is not an answer.

## The sweep artifact: `results/sweep_smollm2_posttraining/`

`probes/abstention_battery.json` holds 32 probes (15 answerable, 15
unanswerable, 2 format) drawn from llm-posttraining's eval parquet —
synthetic-drug QA where abstention is the trained correct response on
unanswerable items. The same battery ran against three staged
post-training checkpoints (SmolLM2-135M, greedy decode):

| stage | answerable | format | unanswerable |
|---|---|---|---|
| sft | 0.27 (degenerate:11 pass:4) | 0.00 | 1.00 (abstains:15) |
| dpo | 0.00 (degenerate:14 fail:1) | 0.00 | 0.13 (abstains:2 degenerate:13) |
| grpo | 0.00 (degenerate:15) | 0.00 | 1.00 (abstains:15) |

What the log actually shows, reading record-level outputs:

- **Abstention is the most robust learned behavior.** SFT and GRPO
  abstain cleanly on all 15 unanswerable probes; DPO nearly destroys it
  (2/15, rest degenerate token loops like `I I I I I`).
- **Answer generation degenerates at every stage.** SFT echoes the
  correct context sentence then loops; GRPO emits answer+abstain mashups
  (abstention bleeding into answerable items); DPO collapses hardest.
- **OOD format instructions fail everywhere** — the checkpoints only
  handle the trained context-bound QA shape.
- **The stage that matters is DPO**: the mid-series checkpoint degraded
  both behaviors simultaneously. A training-run assessment run at that
  stage is what catches it.

This is a mechanics demonstration on a 135M model with synthetic data —
stage-to-stage divergence is the signal, not the absolute numbers.
