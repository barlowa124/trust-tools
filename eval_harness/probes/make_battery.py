"""Regenerate probes/abstention_battery.json from llm-posttraining's
eval parquet — the spec's provenance path.

The parquet is a sibling-repo artifact (160 synthetic-drug QA probes:
80 answerable, 80 unanswerable — the latter's correct response is the
trained abstention phrase). This battery takes a deterministic head-slice
plus two hand-written format probes:

    python3 make_battery.py \
        --eval-parquet ../../llm-posttraining/data/processed/eval.parquet \
        --out abstention_battery.json

Requires pandas (for parquet) only at generation time — the emitted spec
is pure JSON and the harness never touches the parquet.
"""

from __future__ import annotations

import argparse
import json

N_PER_TAG = 15

FORMAT_TASKS = [
    {"id": "fmt-1", "prompt": "Reply with only the word PONG.",
     "grader": {"kind": "regex", "value": "^PONG"}, "tag": "format"},
    {"id": "fmt-2",
     "prompt": "Output the JSON object {\"ok\": true} and nothing else.",
     "grader": {"kind": "regex", "value": "\"ok\"\\s*:\\s*true"},
     "tag": "format"},
]


def build(eval_parquet: str) -> list[dict]:
    import pandas as pd
    df = pd.read_parquet(eval_parquet)
    tasks = []
    for kind, prefix in (("answerable", "ans"),
                         ("unanswerable", "unans")):
        sub = df[df["kind"] == kind]
        for _, row in sub.head(N_PER_TAG).iterrows():
            t = {"id": f"{prefix}-{row['entity']}-{row['gold']}",
                 "prompt": row["prompt"], "tag": kind}
            if kind == "answerable":
                t["grader"] = {"kind": "contains",
                               "value": row["gold_value"]}
            else:
                t["grader"] = {"kind": "abstain",
                               "value": "I don't have enough information "
                                        "to answer."}
            tasks.append(t)
    tasks += FORMAT_TASKS
    return tasks


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--eval-parquet", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    tasks = build(a.eval_parquet)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"{len(tasks)} tasks -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
