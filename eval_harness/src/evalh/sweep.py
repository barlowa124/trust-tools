"""Checkpoint sweep: the same probe battery across model stages.

This is the training-run-assessment shape: run identical tasks against
each stage of a post-training series (base -> SFT -> DPO -> ...) and
report per-tag label movement between stages. Divergence between stages —
not the absolute score — is the signal a TRA looks for.
"""

from __future__ import annotations

import json
from typing import Callable

from .runner import run, summarize


def sweep(stages: list[tuple[str, Callable[[str], str], dict]],
          tasks: list[dict]) -> tuple[dict[str, list[dict]], dict]:
    """stages: [(stage_name, generate_fn, model_meta)].

    Returns ({stage: records}, comparison summary).
    """
    all_records: dict[str, list[dict]] = {}
    stage_summaries = []
    for name, gen_fn, meta in stages:
        recs, summ = run(tasks, gen_fn, meta)
        all_records[name] = recs
        summ["stage"] = name
        stage_summaries.append(summ)
    return all_records, {"stages": stage_summaries}


def sweep_table(summary: dict) -> str:
    """Markdown table: stage x tag score matrix plus label counts."""
    stages = summary["stages"]
    tags = sorted({t for s in stages for t in s["per_tag"]})
    lines = ["| stage | " + " | ".join(tags) + " |",
             "|---|" + "---|" * len(tags)]
    for s in stages:
        row = [s["stage"]]
        for t in tags:
            pt = s["per_tag"].get(t)
            if not pt:
                row.append("-")
                continue
            labels = " ".join(f"{k}:{v}" for k, v in
                              sorted(pt["labels"].items()))
            row.append(f"{pt['score']:.2f} ({labels})")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)
