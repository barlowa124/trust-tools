"""scripted-demo backend: deterministic responses built from real results numbers."""
from __future__ import annotations

import json

from oncocs.llm.recorded import ScriptedBackend


def demo_responses(results: dict, split: dict) -> list[str]:
    r = results
    cohort = (
        f"The {r['cohort']} cohort contains {r.get('n_patients')} harmonized patients, "
        f"split into {split['n_train']} training and {split['n_test']} held-out patients "
        f"at seed {r['seed']}.\n\nData concerns:\n"
        + "\n".join(f"- {k}: {v}" for k, v in r["dropped"].items())
    )
    plan = json.dumps({
        "focus_models": list(r["models"].keys()),
        "claims_to_make": ["report the computed metrics"],
        "must_disclose": [c["name"] for c in r["checks"] if not c["passed"]]})

    metric_lines = []
    for name, out in r["models"].items():
        m = out["metrics"]
        if m.get("abstained"):
            metric_lines.append(f"- {name}: abstained ({m['reason']})")
        else:
            metric_lines.append(
                f"- {name}: Harrell C {m['harrell_c']:.3f}, Uno C {m['uno_c']:.3f}, "
                f"AUC 24m {m['auc_24m']:.3f}, IBS {m['integrated_brier_6_36m']:.3f}")
    failed = [c["name"] for c in r["checks"] if not c["passed"]]
    checks_text = ("All checks passed: "
                   + ", ".join(c["name"] for c in r["checks"]) + ".") if not failed else \
                  ("Failed checks (" + ", ".join(failed) +
                   "): the affected metrics are abstained and not interpreted.")
    draft = (
        f"## Cohort\n{cohort}\n\n"
        f"## Models and metrics\n" + "\n".join(metric_lines) + "\n\n"
        f"## Checks and abstentions\n{checks_text}\n\n"
        "## Limitations\nRetrospective public cohort; research and education use only. "
        "Not for clinical use."
    )
    return [cohort, plan, draft, draft, draft]


def demo_backend(results: dict, split: dict) -> ScriptedBackend:
    b = ScriptedBackend(demo_responses(results, split))
    b.model_id = "scripted-demo"
    return b
