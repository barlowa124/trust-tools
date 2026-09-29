"""evalh command line.

  evalh run --tasks spec.json --out run.jsonl [--model-dir DIR]
            [--generate-fn mod:fn]
            [--api-base URL --api-model NAME]
  evalh sweep --tasks spec.json --model-dirs A,B,C --out-dir out/
  evalh verify run.jsonl
  evalh report summary.json [--md out.md]
  evalh inspect-export --tasks spec.json --out-dir DIR
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys

from .runner import check_log, load_log
from .sweep import sweep, sweep_table
from .tasks import load_tasks


def _import_fn(spec: str):
    mod, _, name = spec.partition(":")
    return getattr(importlib.import_module(mod), name)


def _write_jsonl(records, path):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="evalh")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run", help="run a task spec against one model")
    s.add_argument("--tasks", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--summary")
    s.add_argument("--model-dir")
    s.add_argument("--generate-fn",
                   help="module:function returning prompt->text; "
                        "overrides --model-dir")
    s.add_argument("--api-base",
                   help="OpenAI-compatible API base (e.g. "
                        "https://api.openai.com or a local vLLM server)")
    s.add_argument("--api-model", help="model name for the API endpoint")
    s.add_argument("--max-new-tokens", type=int, default=60)

    s = sub.add_parser("sweep", help="same battery across model dirs")
    s.add_argument("--tasks", required=True)
    s.add_argument("--model-dirs", required=True,
                   help="comma-separated dirs; optional name=dir")
    s.add_argument("--out-dir", required=True)
    s.add_argument("--max-new-tokens", type=int, default=60)

    s = sub.add_parser("inspect-export",
                       help="emit an Inspect dataset.jsonl + task module")
    s.add_argument("--tasks", required=True)
    s.add_argument("--out-dir", required=True)

    s = sub.add_parser("shadow-report",
                       help="grade shadow divergences in a serve log")
    s.add_argument("--log", required=True,
                   help="modelserve serve_response JSONL")
    s.add_argument("--tasks", required=True,
                   help="evalh spec the prompts came from")

    s = sub.add_parser("verify", help="check a run log's chain")
    s.add_argument("log")

    s = sub.add_parser("report", help="markdown table from a sweep summary")
    s.add_argument("summary")
    s.add_argument("--md")

    a = p.parse_args(argv)

    if a.cmd == "run" and not (a.generate_fn or a.model_dir
                               or (a.api_base and a.api_model)):
        print("need --model-dir, --generate-fn, or --api-base+--api-model",
              file=sys.stderr)
        return 2

    if a.cmd == "run":
        tasks = load_tasks(a.tasks)
        if a.generate_fn:
            gen_fn = _import_fn(a.generate_fn)
            model = {"generate_fn": a.generate_fn}
        elif a.api_base:
            if not a.api_model:
                print("--api-base needs --api-model", file=sys.stderr)
                return 2
            from . import api
            gen_fn = api.make_generate_fn(a.api_base, a.api_model,
                                          max_tokens=a.max_new_tokens)
            model = api.model_meta(a.api_base, a.api_model)
        else:
            from . import hf
            gen_fn = hf.make_generate_fn(a.model_dir, a.max_new_tokens)
            model = hf.model_meta(a.model_dir)
        from .runner import run
        records, summary = run(tasks, gen_fn, model,
                               generation={"max_new_tokens":
                                           a.max_new_tokens,
                                           "do_sample": False})
        _write_jsonl(records, a.out)
        if a.summary:
            with open(a.summary, "w") as f:
                json.dump(summary, f, indent=2)
        print(f"{len(records)} results, score={summary['score']:.3f} "
              f"-> {a.out}", file=sys.stderr)
        return 0

    if a.cmd == "sweep":
        from . import hf
        tasks = load_tasks(a.tasks)
        stages = []
        for spec in a.model_dirs.split(","):
            spec = spec.strip()
            name, _, d = spec.partition("=")
            if not d:
                d = name
            else:
                name = name.strip()
            stages.append((name, hf.make_generate_fn(d, a.max_new_tokens),
                           hf.model_meta(d)))
        recs, summary = sweep(stages, tasks)
        import os
        os.makedirs(a.out_dir, exist_ok=True)
        for name, records in recs.items():
            safe = name.replace("/", "_")
            _write_jsonl(records, f"{a.out_dir}/{safe}.jsonl")
        with open(f"{a.out_dir}/sweep_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        with open(f"{a.out_dir}/sweep_summary.md", "w") as f:
            f.write("# Checkpoint sweep\n\n" + sweep_table(summary) + "\n")
        print(sweep_table(summary), file=sys.stderr)
        return 0

    if a.cmd == "verify":
        problems = check_log(load_log(a.log))
        for x in problems:
            print(x, file=sys.stderr)
        n = len(load_log(a.log))
        print(f"{n} records, "
              f"{'OK' if not problems else f'{len(problems)} problems'}",
              file=sys.stderr)
        return 0 if not problems else 1

    if a.cmd == "inspect-export":
        from .inspect_bridge import export
        out = export(a.tasks, a.out_dir)
        print(f"{out['n_tasks']} tasks -> {out['dataset']}, "
              f"{out['task_module']}", file=sys.stderr)
        return 0

    if a.cmd == "shadow-report":
        from .shadow import grade_shadow, shadow_table
        rep = grade_shadow(a.log, load_tasks(a.tasks))
        print(shadow_table(rep))
        print(json.dumps(rep, indent=2), file=sys.stderr)
        return 0

    if a.cmd == "report":
        summary = json.load(open(a.summary, encoding="utf-8"))
        md = "# Checkpoint sweep\n\n" + sweep_table(summary) + "\n"
        if a.md:
            open(a.md, "w").write(md)
        else:
            print(md)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
