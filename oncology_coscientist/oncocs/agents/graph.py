"""LangGraph agent pipeline: LLM drafting nodes + deterministic verify/gate nodes."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from oncocs import evidence
from oncocs.agents.verifier import flatten_results, verify_draft
from oncocs.data.download import load_manifest
from oncocs.splits import load_split, split_sha256

MAX_ATTEMPTS = 3
RETRY_TEMPERATURE = 0.9


class AgentState(TypedDict, total=False):
    cohort: str
    results_path: str
    root: str
    results: dict
    split: dict
    flat_values: dict
    table_text: str
    cohort_summary: str
    passages: dict
    analysis_plan: dict
    analysis_plan_fallback: bool
    analysis_plan_dropped_focus_models: list
    draft: str
    drafts: list
    verification: dict
    attempts: int
    status: str


def _parse_json(text: str) -> dict:
    """Parse a JSON object, tolerating ```json fences and surrounding prose."""
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start = s.find("{")
        if start == -1:
            raise
        depth = 0
        for i, ch in enumerate(s[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(s[start:i + 1])
        raise


def _chat(backend, system: str, user: str, seed: int | None,
          extra_user: str | None = None,
          temperature: float = 0.0) -> str:
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    if extra_user is not None:
        messages.append({"role": "user", "content": extra_user})
    return backend.complete(messages, temperature=temperature, seed=seed)


def render_table(results: dict, split: dict) -> str:
    """Display-precision rendering of everything the LLM may cite."""
    lines = []
    lines.append(f"cohort: {results['cohort']}")
    lines.append(f"seed: {results['seed']}")
    lines.append(f"n_train: {split['n_train']}")
    lines.append(f"n_test: {split['n_test']}")
    for k in ("n_patients", "n_patients_with_expression", "n_unsequenced_patients"):
        if results.get(k) is not None:
            lines.append(f"{k}: {results[k]}")
    # zeros are omitted: "no missing X" entries invite the model to write
    # evaluative claims about data completeness ("absence of missing data
    # suggests a robust analysis")
    lines.append("dropped: " + json.dumps(
        {k: v for k, v in results["dropped"].items() if v}))
    lines.append("missingness: " + json.dumps(
        {k: v for k, v in results["missingness"].items()
         if v.get("missing")}))
    lines.append("checks:")
    for c in results["checks"]:
        if c["passed"]:
            lines.append(f"  {c['name']}: PASS")
        else:
            reason = c["detail"].get("reason", json.dumps(c["detail"]))
            lines.append(f"  {c['name']}: FAIL — {reason} "
                         "(affected models abstained)")
    for name, out in results["models"].items():
        m = out["metrics"]
        if m.get("abstained"):
            lines.append(f"{name}: abstained ({m['reason']})")
            continue
        pairs = " | ".join(f"{k} {v:.3f}" for k, v in m.items()
                           if k != "calibration_24m")
        lines.append(f"{name}: {pairs}")
        for h in out.get("hazard_ratios", []):
            lines.append(f"{name}.HR[{h['covariate']}] = {h['hazard_ratio']:.2f} "
                         f"[{h['hr_ci_lower']:.2f}, {h['hr_ci_upper']:.2f}] "
                         f"p={h['p']:.4f}")
        if out.get("reference_levels"):
            lines.append(f"{name}.reference_levels = {json.dumps(out['reference_levels'])}")
    return "\n".join(lines)


def _plan_view(plan: dict) -> dict:
    """Prompt view of the analysis plan with claim digits masked.

    claims_to_make is free text a small planner can fill with invented
    numbers; the report agent must never see those as citeable values.
    """
    view = json.loads(json.dumps(plan or {}))
    view["claims_to_make"] = [re.sub(r"\d", "#", c)
                              for c in view.get("claims_to_make", [])]
    return view


def build_graph(backend, seed: int | None = None):
    def cohort_agent(state: AgentState) -> dict:
        r = state["results"]
        user = (
            f"Cohort: {r['cohort']}\n"
            f"missingness: {json.dumps(r['missingness'])}\n"
            f"dropped: {json.dumps(r['dropped'])}\n"
            f"n_train: {state['split']['n_train']}, n_test: {state['split']['n_test']}\n"
            f"patients: {r.get('n_patients')}, "
            f"with_expression: {r.get('n_patients_with_expression')}, "
            f"unsequenced: {r.get('n_unsequenced_patients')}\n"
            f"checks: {json.dumps([(c['name'], c['passed']) for c in r['checks']])}\n\n"
            "Write a 1-2 paragraph description of this cohort, then a bulleted list of "
            "data concerns. Use only the numbers above; do not invent any."
        )
        return {"cohort_summary": _chat(
            backend,
            "You are a careful scientific writer. Use only provided numbers.", user, seed)}

    def context_agent(state: AgentState) -> dict:
        """Deterministic: retrieve top-5 PDQ passages for the cohort."""
        from oncocs.config import load_cohort
        from oncocs.rag.retrieve import retrieve
        cfg = load_cohort(state["cohort"], state["root"])
        passages = retrieve(cfg.rag_query, state["root"], mode=cfg.rag_mode) \
            if cfg.rag_query else {}
        return {"passages": passages}

    def analysis_agent(state: AgentState) -> dict:
        r = state["results"]
        menu = {"models": list(r["models"].keys()),
                "metrics": ["harrell_c", "uno_c", "auc_12m", "auc_24m", "auc_36m",
                            "integrated_brier_6_36m"],
                "checks": [{"name": c["name"], "passed": c["passed"]} for c in r["checks"]]}
        user = ("Choose what to discuss from this menu of already-computed items "
                "(you cannot request new computations):\n" + json.dumps(menu, indent=1) +
                "\nRespond with ONLY a JSON object: "
                '{"focus_models": [...], "claims_to_make": [...], "must_disclose": [...]}\n'
                "claims_to_make lists which metrics to report for which models, e.g. "
                '"harrell_c and auc_24m for cox/clinical". Never put numbers in '
                "claims: you have not seen any results, so any number would be "
                "invented.")
        resp = _chat(backend, "You are a planning agent. Reply with JSON only.", user, seed)
        try:
            plan = _parse_json(resp)
        except json.JSONDecodeError as exc:
            resp2 = _chat(backend, "You are a planning agent. Reply with JSON only.",
                          user, seed,
                          extra_user=f"Your previous reply was not valid JSON ({exc}). "
                                     "Return ONLY the JSON object.")
            try:
                plan = _parse_json(resp2)
            except json.JSONDecodeError:
                return {"analysis_plan": {
                            "focus_models": menu["models"],
                            "claims_to_make": ["report all computed metrics"],
                            "must_disclose": [c["name"] for c in r["checks"]
                                              if not c["passed"]]},
                        "analysis_plan_fallback": True}
        focus = [m for m in plan.get("focus_models", []) if m in r["models"]]
        dropped = [m for m in plan.get("focus_models", []) if m not in r["models"]]
        plan["focus_models"] = focus
        return {"analysis_plan": plan,
                "analysis_plan_dropped_focus_models": dropped}

    def modeling_node(state: AgentState) -> dict:
        """Deterministic: confirm recorded hashes still match files on disk."""
        root = Path(state["root"])
        r = state["results"]
        from oncocs.config import load_cohort
        cfg = load_cohort(state["cohort"], root)
        problems = []
        manifest = load_manifest(cfg, root)
        canon = json.dumps({k: v for k, v in manifest.items() if k != "manifest_sha256"},
                           sort_keys=True).encode()
        if hashlib.sha256(canon).hexdigest() != r["data_manifest_sha256"]:
            problems.append("data_manifest_sha256 mismatch")
        split = load_split(cfg, root)
        if split_sha256(split["train_ids"], split["test_ids"]) != r["split_sha256"]:
            problems.append("split_sha256 mismatch")
        flat = flatten_results(r)
        flat.update({f"split.{k}": float(split[k]) for k in ("n_train", "n_test")})
        if problems:
            return {"status": "abstained",
                    "verification": {"passed": False, "hash_problems": problems}}
        return {"flat_values": flat,
                "table_text": render_table(r, split)}

    def report_agent(state: AgentState) -> dict:
        attempts = state.get("attempts", 0) + 1
        system = (
            "You write cautious scientific summaries. Every number in your output must "
            "come from the supplied results table exactly as displayed. If any check "
            "failed, state the corresponding metrics as abstained. Forbidden phrasing: "
            "'clinically validated', 'proves', 'causes', 'should be used', 'outperforms', "
            "'state-of-the-art', 'robust' (and any derivative of it), and "
            "'significant' — every word on "
            "this list is banned in any context. Never rank or compare models: "
            "report each model's values without judging which is better, "
            "stronger, or best. "
            "Do not name the language model, software versions, "
            "or patient identifiers. "
            "Describe each check by its recorded outcome and detail; do not infer "
            "assumption validity from confidence intervals. "
            "Metric glossary: harrell_c and uno_c are concordance indices measuring "
            "discrimination (rank agreement between predicted risk and observed "
            "survival); auc_12m/24m/36m are time-dependent AUCs measuring "
            "discrimination at that horizon; integrated_brier_6_36m is the overall "
            "accuracy of predicted survival probabilities (lower is better). "
            "Do not discuss calibration at all. Do not call a concordance index a calibration "
            "metric. When citing a model-specific number, name the model key "
            "it belongs to in the same sentence or bullet. Report model-level "
            "metrics only; do not list per-covariate hazard ratios, confidence "
            "intervals, or p-values. A model is abstained only when its table "
            "line literally says 'abstained'; never invent an abstention for a "
            "model whose line carries values, and never attribute an "
            "abstention to a check that passed."
        )
        user = (
            "Results table (numbers at display precision; the sole numeric "
            "source):\n"
            + state["table_text"]
            + "\n\nCohort summary (advisory prose; the table wins on any "
            "conflict, and no number may appear that is absent from the "
            "table):\n" + state["cohort_summary"]
            + "\n\nAnalysis plan (structural only — which models and checks to "
            "cover; any numbers inside it are unverified and must not be "
            "copied):\n" + json.dumps(_plan_view(state["analysis_plan"]))
            + "\n\nWrite a markdown report with exactly these sections, in order:\n"
            "## Cohort\n## Models and metrics\n## Checks and abstentions\n## Limitations\n"
            "The headers must appear verbatim as shown above (## + exact title). "
            "Keep each section to a few sentences or bullets so all four "
            "sections fit in one reply. In '## Models and metrics' every model "
            "in the analysis plan gets one bullet that copies its table line "
            "verbatim ('- ' + the line, which already reads 'model: metric "
            "value | metric value | ...' or 'model: abstained (...)'). "
            "Copy values verbatim even when they look unusual (a low or "
            "below-0.5 score is data, not an error). Report model-level "
            "metrics only. In '## Checks and abstentions' write one short "
            "bullet per check as 'name: PASS/FAIL reason'"
            + (
                "; for every FAIL add that the affected models abstained "
                "(the word 'abstained' must appear in that section)"
                if any(not c["passed"] for c in state["results"]["checks"])
                else " — copy the table's check lines verbatim; do not add "
                     "any model lines here"
            )
            + ". In '## Limitations' write one "
            "bullet per fact only: each nonzero missingness entry, "
            "n_unsequenced_patients if nonzero, and each FAILed check. "
            "State the fact; never write a sentence judging whether the "
            "data or analysis is adequate, complete, or sound."
        )
        if state.get("passages"):
            listed = "\n".join(f"[{tag}] {text}"
                               for tag, text in state["passages"].items())
            example_tag = next(iter(state["passages"]))
            user += (
                "\n\nRetrieved public-domain passages you may cite:\n" + listed +
                "\n\nOptionally append a '## Context' section after Limitations. "
                "Cite by paraphrase only: write the claim in your own words and "
                f"end the sentence with the bare tag, e.g. ... [{example_tag}]. "
                "Never put passage text in quotation marks; never cite a tag "
                "not listed above; numbers in Context must come from the "
                "cited passage, not the results table. If Context would "
                "contain any table number, omit the section entirely.")
        extra = None
        if state.get("verification") and not state["verification"].get("passed", True):
            v = state["verification"]
            findings = []
            for u in v.get("unverified_numbers", []):
                findings.append(f"  - {u['token']} (context: {u['context']})")
            if any("context section" in str(u.get("context", ""))
                   for u in v.get("unverified_numbers", [])):
                findings.append("  - numbers found in the Context section "
                                "came from the results table — delete the "
                                "Context section entirely")
            if v.get("unverified_numbers"):
                findings.append("  - every number must be copied from a table "
                                "line. A model whose table line says "
                                "'abstained' has no metrics: write "
                                "'abstained', not values.")
            for u in v.get("unscoped_model_numbers", []):
                findings.append(f"  - The number {u['token']} only exists under "
                                f"model results ({', '.join(u['found_in'])}); cite it "
                                "inside a block that names that model.")
            for ma in v.get("misattributed", []):
                findings.append(f"  - The number {ma['token']} appears under "
                                f"{ma['attributed_to']} but belongs to "
                                f"{', '.join(ma['actually_in'])}.")
            for fm in v.get("missing_focus_models", []):
                findings.append(f"  - model {fm} was in the analysis plan but is "
                                "never discussed")
            for fm in v.get("focus_without_values", []):
                metrics = sorted(k.rsplit(".", 1)[1]
                                 for k in state.get("flat_values", {})
                                 if k.startswith(f"models.{fm}.metrics."))
                hint = f" (e.g. {', '.join(metrics[:4])})" if metrics else ""
                findings.append(f"  - add a bullet starting with '{fm}:' that "
                                f"lists its own metric values from the table{hint}")
            for fm in v.get("false_abstention", []):
                findings.append(f"  - the rejected draft says {fm} is "
                                "abstained, but its table line carries metric "
                                "values — copy that line verbatim")
            for f in v.get("unknown_citations", []):
                findings.append(f"  - citation tag {f} was not among the retrieved passages")
            for f in v.get("misquotes", []):
                findings.append(f"  - quoted text does not match passage {f['tag']}: "
                                f"{f['quote'][:60]!r}")
            for f in v.get("forbidden", []):
                findings.append(f"  - forbidden phrasing: {f}")
            for s in v.get("missing_sections", []):
                findings.append(f"  - missing section: {s}")
            if v.get("abstention_missing"):
                findings.append("  - a failed check must be disclosed as an abstention")
            extra = (f"Rewrite attempt {attempts}. The report below was "
                     "rejected by an automated checker.\n\n"
                     "<rejected_draft>\n" + state["draft"] +
                     "\n</rejected_draft>\n\n"
                     "Write the report again from scratch — do not reuse "
                     "sentences from the rejected draft. Fix every problem "
                     "below; never copy this list, its bullets, or checker "
                     "phrasing into the report:\n" + "\n".join(findings))
        # retries sample at a small temperature: at temp 0 a rejected draft
        # tends to regenerate token-identical text, so identical findings
        # would loop forever — sampling is what makes the retry real.
        return {"draft": _chat(backend, system, user, seed, extra_user=extra,
                               temperature=RETRY_TEMPERATURE if extra else 0.0),
                "attempts": attempts}

    def claim_verifier(state: AgentState) -> dict:
        v = verify_draft(state["draft"], state["flat_values"], state["results"]["checks"],
                         models=state["results"].get("models"),
                         focus_models=(state.get("analysis_plan") or {})
                         .get("focus_models"),
                         passages=state.get("passages") or {})
        drafts = list(state.get("drafts", []))
        drafts.append({"attempt": state["attempts"], "draft": state["draft"],
                       "verification": v})
        out = {"verification": v, "drafts": drafts}
        if v["passed"]:
            out["status"] = "draft_pending_approval"
        elif state["attempts"] >= MAX_ATTEMPTS:
            out["status"] = "rejected"
        return out

    def route_after_verify(state: AgentState):
        if state.get("status") in ("draft_pending_approval", "rejected"):
            return "human_gate"
        return "report_agent"

    def human_gate(state: AgentState) -> dict:
        return {}

    g = StateGraph(AgentState)
    g.add_node("cohort_agent", cohort_agent)
    g.add_node("context_agent", context_agent)
    g.add_node("analysis_agent", analysis_agent)
    g.add_node("modeling_node", modeling_node)
    g.add_node("report_agent", report_agent)
    g.add_node("claim_verifier", claim_verifier)
    g.add_node("human_gate", human_gate)
    g.set_entry_point("cohort_agent")
    g.add_edge("cohort_agent", "context_agent")
    g.add_edge("context_agent", "analysis_agent")
    g.add_edge("analysis_agent", "modeling_node")
    g.add_conditional_edges(
        "modeling_node",
        lambda s: END if s.get("status") == "abstained" else "report_agent")
    g.add_edge("report_agent", "claim_verifier")
    g.add_conditional_edges("claim_verifier", route_after_verify)
    g.add_edge("human_gate", END)
    return g.compile()


UNAPPROVED_BANNER = "> **UNAPPROVED DRAFT - pending human review**"


def render_report_md(draft: str, agent_run_sha256: str | None = None,
                     approval: dict | None = None,
                     status: str = "draft_pending_approval",
                     drafts: list | None = None) -> str:
    meta = f"<!-- agent_run_sha256: {agent_run_sha256} -->\n" if agent_run_sha256 else ""
    if status == "rejected":
        lines = [f"> **REJECTED - no verified report was produced after "
                 f"{len(drafts or [])} attempts.**", ""]
        for d in drafts or []:
            v = d["verification"]
            findings = []
            findings += [f"unverified number {u['token']!r} ({u['context']})"
                         for u in v.get("unverified_numbers", [])]
            findings += [f"unscoped model number {u['token']!r} "
                         f"(belongs to {', '.join(u['found_in'])})"
                         for u in v.get("unscoped_model_numbers", [])]
            findings += [f"number {ma['token']!r} attributed to "
                         f"{ma['attributed_to']} but belongs to "
                         f"{', '.join(ma['actually_in'])}"
                         for ma in v.get("misattributed", [])]
            findings += [f"focus model {fm} never discussed"
                         for fm in v.get("missing_focus_models", [])]
            findings += [f"unknown citation {t}" for t in v.get("unknown_citations", [])]
            findings += [f"misquote of {mq['tag']}" for mq in v.get("misquotes", [])]
            findings += [f"forbidden phrasing: {f}" for f in v.get("forbidden", [])]
            findings += [f"missing section: {s}" for s in v.get("missing_sections", [])]
            if v.get("abstention_missing"):
                findings.append("failed check not disclosed as abstention")
            lines.append(f"- Attempt {d['attempt']}: "
                         + ("; ".join(findings) or "unknown failure"))
        lines += ["", "All drafts with their verification results are preserved "
                      "in `agent_run.json`."]
        return meta + "\n".join(lines) + "\n"
    if status == "abstained":
        return meta + "> **ABSTAINED - recorded evidence hashes no longer match " \
                      "the files on disk; no report produced.**\n"
    if approval:
        banner = f"> Approved by {approval['by']} on {approval['timestamp'][:10]}"
    else:
        banner = UNAPPROVED_BANNER
    return f"{meta}{banner}\n\n{draft}\n"


def run_agent(cohort: str, results_path: Path, backend, seed: int | None,
              root: Path) -> dict:
    """Run the graph, write agent_run.json + report.md, return the agent record."""
    results = json.loads(Path(results_path).read_text(encoding="utf-8"))
    results_sha = hashlib.sha256(Path(results_path).read_bytes()).hexdigest()
    agent_run_id = uuid.uuid4().hex[:12]
    out_dir = Path(results_path).parent / "agent" / agent_run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    from oncocs.config import load_cohort
    from oncocs.llm.recorded import RecordingBackend
    rec = backend if isinstance(backend, RecordingBackend) else RecordingBackend(backend)
    split = load_split(load_cohort(cohort, root), root)
    graph = build_graph(rec, seed=seed)
    init: AgentState = {"cohort": cohort, "results_path": str(results_path),
                        "root": str(root), "results": results, "split": split,
                        "drafts": [], "attempts": 0, "status": "running"}
    final = graph.invoke(init)

    record = {
        "agent_run_id": agent_run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "cohort": cohort,
        "results_path": str(results_path),
        "results_sha256": results_sha,
        "backend": backend.name,
        "model_id": backend.model_id,
        "temperature": {"first_attempt": 0.0, "retry": RETRY_TEMPERATURE},
        "seed": seed,
        "git_commit": evidence._git_commit(root),
        "git_dirty": evidence._git_dirty(root),
        "transcript": rec.transcript,
        "drafts": final.get("drafts", []),
        "cohort_summary": final.get("cohort_summary"),
        "analysis_plan": final.get("analysis_plan"),
        "analysis_plan_fallback": final.get("analysis_plan_fallback", False),
        "analysis_plan_dropped_focus_models":
            final.get("analysis_plan_dropped_focus_models", []),
        "status": final.get("status"),
        "verification": final.get("verification"),
        "final_report_sha256": None,
    }
    run_path = out_dir / "agent_run.json"
    sha = agent_run_sha(record)
    report_md = render_report_md(final.get("draft", ""), agent_run_sha256=sha,
                                 status=record["status"], drafts=record["drafts"])
    (out_dir / "report.md").write_text(report_md, encoding="utf-8")
    record["final_report_sha256"] = hashlib.sha256(report_md.encode()).hexdigest()
    run_path.write_text(json.dumps(record, indent=2, default=str) + "\n",
                        encoding="utf-8")
    return record


def agent_run_sha(record: dict) -> str:
    """Canonical sha over the agent record, excluding review and report hash."""
    canon = {k: v for k, v in record.items()
             if k not in ("final_report_sha256", "approval", "human_review")}
    return hashlib.sha256(json.dumps(canon, sort_keys=True, default=str).encode()).hexdigest()
