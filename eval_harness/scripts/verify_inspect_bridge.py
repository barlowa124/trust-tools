"""Verify the evalh -> Inspect bridge end to end.

Exports an evalh spec, then runs the generated @task under Inspect's
local mockllm provider twice:

  canned   — mockllm's fixed reply; every grader fails (expected 0.0),
             which proves execution without crediting the model.
  oracle   — per-sample answers chosen to satisfy each evalh grader
             (expected 1.0), which proves the scorer's correct path.

Writes a compact JSON summary for committing. Requires `inspect_ai`
(>=3.10 python) and `evalh` importable; the script is excluded from the
stdlib-only test suite and exercised in the CI job that installs it.

Usage: python scripts/verify_inspect_bridge.py SPEC --out summary.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from itertools import chain

from evalh.graders import grade
from evalh.inspect_bridge import export

# Fallback completions for grader kinds whose target cannot be echoed
# (regex patterns match strings, not the pattern text itself).
_ORACLE_POOL = ["PONG", '{"ok": true}', "0", "yes", "no"]


def _oracle_answers(dataset_path: str) -> list[str]:
    answers = []
    for line in open(dataset_path, encoding="utf-8"):
        row = json.loads(line)
        grader = row["metadata"]["grader"]
        for cand in chain([row["target"]], _ORACLE_POOL):
            if grade(cand, grader)["score"]:
                answers.append(cand)
                break
        else:
            answers.append("")
    return answers


def _load_task(task_module: str):
    """Import the generated module and call its @task function.

    @task keeps the function's own name (the file stem minus
    ``_task``), so find module-local callables and return the one that
    produces a Task.
    """
    from inspect_ai import Task
    spec = importlib.util.spec_from_file_location("t", task_module)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for v in vars(mod).values():
        if callable(v) and getattr(v, "__module__", None) == "t":
            obj = v()
            if isinstance(obj, Task):
                return obj
    raise RuntimeError(f"no @task found in {task_module}")


def _run(task, answers, log_dir):
    from inspect_ai import eval as inspect_eval
    from inspect_ai.log import read_eval_log
    from inspect_ai.model import ModelOutput

    model_args = {}
    if answers is not None:
        it = iter(ModelOutput.from_content("mockllm/model", content=a)
                  for a in answers)
        model_args["custom_outputs"] = it
    [log] = inspect_eval(tasks=[task], model="mockllm/model",
                         model_args=model_args, log_dir=log_dir,
                         display="none")
    log = read_eval_log(log.location) if hasattr(log, "location") else log
    n = len(log.samples)
    n_corr = sum(1 for s in log.samples
                 if s.scores["evalh_grade"].value == "C")
    return {"status": log.status, "n_samples": n, "n_correct": n_corr}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out_path = os.path.abspath(a.out)

    with tempfile.TemporaryDirectory() as td:
        exp = export(a.spec, td)
        os.chdir(td)
        task = _load_task(exp["task_module"])
        answers = _oracle_answers(exp["dataset"])
        summary = {
            "spec": os.path.basename(a.spec),
            "n_tasks": exp["n_tasks"],
            "canned": _run(task, None, os.path.join(td, "logs")),
            "oracle": _run(task, answers, os.path.join(td, "logs")),
        }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps(summary, indent=1))
    ok = (summary["canned"]["n_correct"] == 0
          and summary["oracle"]["n_correct"] == summary["n_tasks"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
