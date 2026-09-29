# inspect_bundle: loadable Inspect tasks

Ready-to-run Inspect (inspect_ai) tasks exported from evalh specs by
`evalh inspect-export`. Each directory holds `dataset.jsonl` plus a
`*_task.py` `@task` whose scorer wraps evalh's deterministic graders,
so results are comparable across the two eval tools.

```bash
pip install inspect_ai .   # evalh must be importable for scoring
cd abstention_battery
inspect eval abstention_battery_task.py --model <provider/model>
```

| Task | Samples | Grader coverage |
|---|---|---|
| `abstention_battery` | 32 | contains, abstain, regex |
| `injection_battery` | 10 | not_contains on injected tool output, plus controls |
| `format_battery` | 7 | exact/regex output-format checks |

Verified under Inspect's local `mockllm` provider, no API key needed:
`scripts/verify_inspect_bridge.py` runs each task twice (canned reply
and a grader-aware oracle) and the summaries in `../validation/` show
oracle passes at 100% in all three. `canned` counts differ per battery
by design: mockllm's inert reply should fail content graders but does
trivially satisfy `not_contains` probes.
