"""modelserve command line.

Offline replay exercises the same service code as the API path — useful
for demos and CI where standing a server up is overkill:

  modelserve replay --prompts prompts.txt [--generate-fn mod:fn]
                    [--model-dir DIR] [--shadow-dir DIR]
                    [--shadow-fraction 0.5] [--out records.jsonl]
  modelserve verify records.jsonl
  modelserve serve --model-dir DIR [--shadow-dir DIR] [--port 8000]
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys

from .service import Service


def _import_fn(spec: str):
    mod, _, name = spec.partition(":")
    return getattr(importlib.import_module(mod), name)


def _model_fn(args, attr="model_dir"):
    """Resolve generate_fn + model meta from CLI args."""
    gen_spec = getattr(args, "generate_fn", None)
    d = getattr(args, attr, None)
    if gen_spec:
        return _import_fn(gen_spec), {"generate_fn": gen_spec}
    from .hf import make_generate_fn, model_meta
    return make_generate_fn(d), model_meta(d)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="modelserve")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("replay", help="run prompts through the service, "
                       "write the receipt chain")
    s.add_argument("--prompts", required=True,
                   help="one prompt per line")
    s.add_argument("--model-dir")
    s.add_argument("--generate-fn")
    s.add_argument("--shadow-dir")
    s.add_argument("--shadow-fraction", type=float, default=1.0)
    s.add_argument("--batch-size", type=int, default=8)
    s.add_argument("--out", default="-")
    s.add_argument("--report")

    s = sub.add_parser("verify", help="check a response record chain")
    s.add_argument("log")

    s = sub.add_parser("serve", help="run the FastAPI app")
    s.add_argument("--model-dir", required=True)
    s.add_argument("--shadow-dir")
    s.add_argument("--shadow-fraction", type=float, default=0.1)
    s.add_argument("--port", type=int, default=8000)

    a = p.parse_args(argv)

    for cmd, attr in (("replay", "model_dir"), ("serve", "model_dir")):
        if a.cmd == cmd and not getattr(a, "generate_fn", None) \
                and not getattr(a, attr, None):
            print(f"need --{attr.replace('_', '-')} or --generate-fn",
                  file=sys.stderr)
            return 2

    if a.cmd == "replay":
        gen_fn, model = _model_fn(a)
        shadow_fn, shadow_model = (None, None)
        if a.shadow_dir:
            shadow_fn, shadow_model = _model_fn(a, "shadow_dir")
        svc = Service(gen_fn, model, shadow_fn=shadow_fn,
                      shadow_model=shadow_model,
                      shadow_fraction=a.shadow_fraction,
                      batch_size=a.batch_size)
        svc.start()
        prompts = [l.rstrip("\n") for l in open(a.prompts)
                   if l.strip()]
        for prompt in prompts:
            svc.infer(prompt)
        svc.stop()
        out = sys.stdout if a.out == "-" else open(a.out, "w")
        for r in svc.records:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
        rep = svc.report()
        if a.report:
            with open(a.report, "w") as f:
                json.dump(rep, f, indent=2)
        else:
            print(json.dumps(rep, indent=2), file=sys.stderr)
        return 0

    if a.cmd == "verify":
        svc = Service(lambda x: x, {})  # unused; checking loaded records
        svc._records = [json.loads(l) for l in open(a.log) if l.strip()]
        problems = svc.check_chain()
        for x in problems:
            print(x, file=sys.stderr)
        print(f"{len(svc.records)} records, "
              f"{'OK' if not problems else f'{len(problems)} problems'}",
              file=sys.stderr)
        return 0 if not problems else 1

    if a.cmd == "serve":
        gen_fn, model = _model_fn(a)
        shadow_fn, shadow_model = (None, None)
        if a.shadow_dir:
            shadow_fn, shadow_model = _model_fn(a, "shadow_dir")
        svc = Service(gen_fn, model, shadow_fn=shadow_fn,
                      shadow_model=shadow_model,
                      shadow_fraction=a.shadow_fraction)
        svc.start()
        from .app import build_app
        import uvicorn
        uvicorn.run(build_app(svc), host="127.0.0.1", port=a.port)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
