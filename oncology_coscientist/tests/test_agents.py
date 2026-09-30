"""Offline tests for the agent layer. ScriptedBackend only, no Ollama needed."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from oncocs.agents.approve import approve
from oncocs.agents.graph import UNAPPROVED_BANNER, run_agent
from oncocs.agents.replay import replay_agent
from oncocs.agents.verifier import verify_draft
from oncocs.llm.recorded import ScriptedBackend

SEED = 20240601


@pytest.fixture()
def synth_results(synth_split):
    """A real results.json produced by the synthetic pipeline."""
    from tests.test_pipeline import _run
    r = _run(synth_split)
    return synth_split / "results" / "synth" / r["run_id"] / "results.json"


# ---------- verifier ----------

FLAT = {"models.cox.harrell_c": 0.6466, "models.cox.p": 0.0248,
        "n_patients": 501.0, "models.cox.auc_24m": 0.6912}
GOOD = ("## Cohort\n501 patients.\n\n## Models and metrics\nHarrell C 0.647, "
        "AUC at 24 months 0.691.\n\n## Checks and abstentions\nAll checks passed.\n\n"
        "## Limitations\nResearch only.")


def test_verifier_accepts_correct_numbers():
    assert verify_draft(GOOD, FLAT, [])["passed"]


def test_verifier_accepts_percentage():
    d = GOOD.replace("0.647", "64.7%")
    assert verify_draft(d, FLAT, [])["passed"]


def test_verifier_rejects_fabricated_number():
    d = GOOD.replace("0.647", "0.892")
    v = verify_draft(d, FLAT, [])
    assert not v["passed"] and v["unverified_numbers"]


def test_verifier_rejects_sign_flip():
    # "-0.647" must not verify against +0.6466, and vice versa.
    d = GOOD.replace("0.647", "-0.647")
    v = verify_draft(d, FLAT, [])
    assert not v["passed"] and v["unverified_numbers"]
    neg_flat = dict(FLAT, **{"models.cox.harrell_c": -0.6466})
    d2 = GOOD.replace("0.647", "-0.647")
    assert verify_draft(d2, neg_flat, [])["passed"]
    # hyphenated ranges still extract both endpoints unsigned
    rng = GOOD.replace("0.647", "0.647-0.691")
    assert verify_draft(rng, FLAT, [])["passed"]


def test_verifier_misquote_tag_then_quote():
    # tag-then-quote ordering must get the same verbatim check as
    # quote-then-tag
    passages = {"PDQ:doc#0": "Median survival was 18 months."}
    good = GOOD + '\n\n## Context\n[PDQ:doc#0] "Median survival was 18 months."'
    bad = GOOD + '\n\n## Context\n[PDQ:doc#0] "Median survival was 24 months."'
    v_ok = verify_draft(good, FLAT, [], passages=passages)
    assert not v_ok["misquotes"] and v_ok["passed"]
    v_bad = verify_draft(bad, FLAT, [], passages=passages)
    assert v_bad["misquotes"] and not v_bad["passed"]


def test_verifier_rejects_forbidden_and_missing():
    assert "outperforms" in verify_draft(GOOD + " outperforms baselines", FLAT, [])["forbidden"]
    missing = verify_draft(GOOD.replace("## Cohort", "## Data"), FLAT, [])
    assert "## Cohort" in missing["missing_sections"]


def test_verifier_sections_case_insensitive():
    d = GOOD.replace("## Models and metrics", "## Models and Metrics  ")
    assert verify_draft(d, FLAT, [])["passed"]


def test_verifier_abstention_and_significant():
    checks = [{"name": "proportional_hazards", "passed": False}]
    v = verify_draft(GOOD, FLAT, checks)
    assert not v["passed"] and v["abstention_missing"]
    ok = GOOD.replace("All checks passed.",
                      "proportional_hazards failed; Cox HRs are abstained.")
    assert verify_draft(ok, FLAT, checks)["passed"]
    # 'significant' requires a verifying p-value within 40 chars
    sig_ok = GOOD + "\nThe effect was significant (p=0.0248)."
    assert verify_draft(sig_ok, FLAT, [])["passed"]
    sig_bad = GOOD + "\nThe effect was significant (p=0.9999)."
    assert not verify_draft(sig_bad, FLAT, [])["passed"]


# ---------- graph ----------

def _run_path(results_path, rec):
    return (Path(results_path).parent / "agent" / rec["agent_run_id"]
            / "agent_run.json")


def _report_path(results_path, rec):
    return _run_path(results_path, rec).parent / "report.md"


def _agent_run(root, results_path, responses, seed=SEED):
    from oncocs.llm.recorded import RecordingBackend
    backend = RecordingBackend(ScriptedBackend(responses))
    return run_agent("synth", results_path, backend, seed, root)


def _scripted_ok(results_path):
    r = json.loads(Path(results_path).read_text())
    from oncocs.agents.demo import demo_responses
    from oncocs.config import load_cohort
    from oncocs.splits import load_split
    split = load_split(load_cohort("synth", results_path.parents[3]), results_path.parents[3])
    return demo_responses(r, split)


def test_graph_passes_and_writes_banner(synth_results):
    rec = _agent_run(synth_results.parents[3], synth_results, _scripted_ok(synth_results))
    assert rec["status"] == "draft_pending_approval"
    md = _report_path(synth_results, rec).read_text(encoding="utf-8")
    assert UNAPPROVED_BANNER in md


def test_graph_rejected_after_three_attempts(synth_results):
    bad_draft = "## Cohort\n0.99999 fabricated.\n" * 4  # unverifiable, missing sections
    responses = ["cohort text", '{"focus_models": []}',
                 bad_draft, bad_draft, bad_draft]
    rec = _agent_run(synth_results.parents[3], synth_results, responses)
    assert rec["status"] == "rejected"
    assert len(rec["drafts"]) == 3
    assert all(not d["verification"]["passed"] for d in rec["drafts"])


def test_analysis_json_fenced_and_fallback(synth_results):
    fenced = '```json\n{"focus_models": ["cox/clinical"], "claims_to_make": [], ' \
             '"must_disclose": []}\n```'
    rec = _agent_run(synth_results.parents[3], synth_results,
                     ["cohort text", fenced, *_scripted_ok(synth_results)[2:]])
    assert rec["analysis_plan"]["focus_models"] == ["cox/clinical"]
    assert not rec["analysis_plan_fallback"]
    responses = ["cohort text", "not json at all", "still not json",
                 *_scripted_ok(synth_results)[2:]]
    rec = _agent_run(synth_results.parents[3], synth_results, responses)
    assert rec["analysis_plan_fallback"] is True


def test_retry_prompt_contains_previous_draft(synth_results):
    bad = "## Cohort\n0.99999 fabricated.\n"
    responses = ["cohort text", '{"focus_models": []}',
                 bad, bad, bad]
    rec = _agent_run(synth_results.parents[3], synth_results, responses)
    assert rec["status"] == "rejected"
    # transcript calls: 0 cohort, 1 analysis, 2..4 report attempts
    second_report_msgs = rec["transcript"][3]["messages"]
    assert any(bad in m["content"] for m in second_report_msgs)


def test_rejected_rendering_and_approve_refusal(synth_results):
    bad = "## Cohort\n0.99999 fabricated.\n"
    rec = _agent_run(synth_results.parents[3], synth_results,
                     ["cohort text", '{"focus_models": []}', bad, bad, bad])
    assert rec["status"] == "rejected"
    md = _report_path(synth_results, rec).read_text(encoding="utf-8")
    assert "REJECTED" in md and UNAPPROVED_BANNER not in md
    assert "agent_run.json" in md
    with pytest.raises(ValueError):
        approve(_run_path(synth_results, rec), by="tester")


def test_modeling_node_abstains_on_tamper(synth_results, tmp_path):
    r = json.loads(synth_results.read_text())
    r["split_sha256"] = "0" * 64
    tampered = tmp_path / "results.json"
    tampered.write_text(json.dumps(r))
    rec = _agent_run(synth_results.parents[3], tampered, _scripted_ok(synth_results))
    assert rec["status"] == "abstained"


# ---------- replay ----------

def test_replay_identical_and_tamper_detected(synth_results):
    rec = _agent_run(synth_results.parents[3], synth_results, _scripted_ok(synth_results))
    run_path = _run_path(synth_results, rec)
    status, msg = replay_agent(run_path)
    assert status == "PASS", msg
    tampered = json.loads(run_path.read_text())
    tampered["transcript"][0]["prompt_sha256"] = "0" * 64
    run_path.write_text(json.dumps(tampered))
    status, msg = replay_agent(run_path)
    assert status == "FROZEN" and msg == "0"


# ---------- approve ----------

def test_approve_and_tamper_refusal(synth_results):
    rec = _agent_run(synth_results.parents[3], synth_results, _scripted_ok(synth_results))
    run_path = _run_path(synth_results, rec)
    approve(run_path, by="tester", note="looks right")
    md = _report_path(synth_results, rec).read_text(encoding="utf-8")
    assert "> Approved by tester" in md and UNAPPROVED_BANNER not in md
    # editing the approved run then trying to approve again must fail
    tampered = json.loads(run_path.read_text())
    tampered.pop("approval")
    tampered["transcript"][0]["elapsed_s"] = 999
    run_path.write_text(json.dumps(tampered))
    with pytest.raises(ValueError):
        approve(run_path, by="attacker")


def test_approve_refuses_modified_report_body(synth_results):
    """Editing report prose while keeping the embedded hash marker must
    block approval: the marker only covers agent_run.json."""
    rec = _agent_run(synth_results.parents[3], synth_results, _scripted_ok(synth_results))
    run_path = _run_path(synth_results, rec)
    rp = _report_path(synth_results, rec)
    rp.write_text(rp.read_text(encoding="utf-8") + "\ninjected paragraph\n",
                  encoding="utf-8")
    with pytest.raises(ValueError):
        approve(run_path, by="attacker")
    assert "approval" not in json.loads(run_path.read_text())


def test_approve_records_post_banner_report_hash(synth_results):
    rec = _agent_run(synth_results.parents[3], synth_results, _scripted_ok(synth_results))
    run_path = _run_path(synth_results, rec)
    approve(run_path, by="tester")
    record = json.loads(run_path.read_text())
    md = _report_path(synth_results, rec).read_bytes()
    assert record["approval"]["report_sha256"] == hashlib.sha256(md).hexdigest()
    # final_report_sha256 still describes the pre-decision rendered bytes
    assert record["final_report_sha256"] == rec["final_report_sha256"]


# ---------- reject ----------

def test_reject_and_mutual_exclusion(synth_results):
    from oncocs.agents.approve import reject
    rec = _agent_run(synth_results.parents[3], synth_results, _scripted_ok(synth_results))
    rp = _run_path(synth_results, rec)
    reject(rp, by="lead", reason="mislabeled block")
    record = json.loads(rp.read_text())
    assert record["human_review"]["decision"] == "rejected"
    assert record["human_review"]["by"] == "lead"
    md = _report_path(synth_results, rec).read_text(encoding="utf-8")
    assert "REJECTED BY HUMAN REVIEWER (lead)" in md
    # approve refuses after reject
    with pytest.raises(ValueError):
        approve(rp, by="someone")
    # reject refuses after approve
    rec2 = _agent_run(synth_results.parents[3], synth_results,
                      _scripted_ok(synth_results))
    rp2 = _run_path(synth_results, rec2)
    approve(rp2, by="tester")
    with pytest.raises(ValueError):
        reject(rp2, by="lead", reason="too late")


def test_reject_refuses_modified_report_body(synth_results):
    from oncocs.agents.approve import reject
    rec = _agent_run(synth_results.parents[3], synth_results, _scripted_ok(synth_results))
    rp = _report_path(synth_results, rec)
    rp.write_text(rp.read_text(encoding="utf-8") + "\ninjected paragraph\n",
                  encoding="utf-8")
    run_path = _run_path(synth_results, rec)
    with pytest.raises(ValueError):
        reject(run_path, by="lead", reason="x")
    assert "human_review" not in json.loads(run_path.read_text())


# ---------- scoped claim verification ----------

SCOPE_FLAT = {"n_patients": 501.0, "split.n_train": 350.0,
              "models.cox/clinical.metrics.harrell_c": 0.647,
              "models.cox/clinical_expression.metrics.harrell_c": 0.643,
              "models.rsf/clinical.metrics.harrell_c": 0.639,
              "models.rsf/clinical_expression.metrics.harrell_c": 0.632}
SCOPE_MODELS = {
    "cox/clinical": {"metrics": {"harrell_c": 0.647}},
    "cox/clinical_expression": {"metrics": {"harrell_c": 0.643}},
    "rsf/clinical": {"metrics": {"harrell_c": 0.639}},
    "rsf/clinical_expression": {"metrics": {"harrell_c": 0.632}},
}
FOCUS_ALL = list(SCOPE_MODELS)


def _scoped_draft(body: str) -> str:
    return ("## Cohort\n501 patients.\n\n## Models and metrics\n" + body +
            "\n\n## Checks and abstentions\nAll checks passed.\n\n"
            "## Limitations\nResearch only.")


def test_scoped_verifier_catches_misattribution():
    # the preserved-run pattern: cox/clinical_expression numbers under an rsf label
    body = ("* cox/clinical: C 0.647\n* rsf/clinical: C 0.639\n"
            "* cox/clinical_expression: C 0.643\n"
            "* rsf/clinical_expression: C 0.643\n")
    v = verify_draft(_scoped_draft(body), SCOPE_FLAT, [], models=SCOPE_MODELS,
                     focus_models=FOCUS_ALL)
    assert not v["passed"]
    ma = v["misattributed"][0]
    assert ma["attributed_to"] == "rsf/clinical_expression"
    assert "cox/clinical_expression" in ma["actually_in"]


def test_scoped_verifier_correct_attribution_and_global_counts():
    body = ("* cox/clinical: C 0.647\n* rsf/clinical: C 0.639\n"
            "* cox/clinical_expression: C 0.643 (n_train 350)\n"
            "* rsf/clinical_expression: C 0.632\n")
    v = verify_draft(_scoped_draft(body), SCOPE_FLAT, [], models=SCOPE_MODELS,
                     focus_models=FOCUS_ALL)
    assert v["passed"], v


def test_scoped_verifier_missing_focus_model():
    body = ("* cox/clinical: C 0.647\n* rsf/clinical: C 0.639\n"
            "* cox/clinical_expression: C 0.643\n")
    v = verify_draft(_scoped_draft(body), SCOPE_FLAT, [], models=SCOPE_MODELS,
                     focus_models=FOCUS_ALL)
    assert not v["passed"]
    assert v["missing_focus_models"] == ["rsf/clinical_expression"]


def test_unscoped_model_number_rejected():
    # 0.639 exists only under models.rsf/clinical; in unscoped text it must fail.
    # (Numbers after the last model mention are scoped to it, so the unscoped
    # mention goes in the Cohort section, before any model key appears.)
    body = ("* cox/clinical: C 0.647\n* rsf/clinical: C 0.639\n"
            "* cox/clinical_expression: C 0.643\n"
            "* rsf/clinical_expression: C 0.632\n")
    draft = ("## Cohort\n501 patients. Overall discrimination reached 0.639 overall.\n\n"
             "## Models and metrics\n" + body +
             "\n\n## Checks and abstentions\nAll checks passed.\n\n"
             "## Limitations\nResearch only.")
    v = verify_draft(draft, SCOPE_FLAT, [], models=SCOPE_MODELS,
                     focus_models=FOCUS_ALL)
    assert not v["passed"]
    assert any(u["token"] == "0.639" for u in v["unscoped_model_numbers"])


def test_model_number_inside_its_block_passes():
    body = ("* cox/clinical: C 0.647\n* rsf/clinical: C 0.639\n"
            "* cox/clinical_expression: C 0.643\n"
            "* rsf/clinical_expression: C 0.632, compared with 0.639\n")
    v = verify_draft(_scoped_draft(body), SCOPE_FLAT, [], models=SCOPE_MODELS,
                     focus_models=FOCUS_ALL)
    # 0.639 inside the rsf/clinical_expression block is misattributed (belongs to
    # rsf/clinical), not unscoped -- the right finding fires either way
    assert v["passed"] or v["misattributed"]


def test_calibration_glossary_misuse_rejected():
    body = ("* cox/clinical: C 0.647\n* rsf/clinical: C 0.639\n"
            "* cox/clinical_expression: C 0.643\n"
            "* rsf/clinical_expression: C 0.632\n\n"
            "The harrell_c metric represents calibration of the predictions.\n")
    v = verify_draft(_scoped_draft(body), SCOPE_FLAT, [], models=SCOPE_MODELS,
                     focus_models=FOCUS_ALL)
    assert not v["passed"]
    assert "C-index described as calibration" in v["forbidden"]


def test_metric_label_integers_are_global():
    # "6-36" from integrated_brier_6_36m is a window label, not a model value
    flat = dict(SCOPE_FLAT)
    for mk in SCOPE_MODELS:
        flat[f"models.{mk}.metrics.integrated_brier_6_36m"] = 0.15
    body = ("* cox/clinical: C 0.647\n* rsf/clinical: C 0.639\n"
            "* cox/clinical_expression: C 0.643\n"
            "* rsf/clinical_expression: C 0.632\n")
    draft = ("## Cohort\n501 patients, scored over 6-36 months overall.\n\n"
             "## Models and metrics\n" + body +
             "\n\n## Checks and abstentions\nAll checks passed.\n\n"
             "## Limitations\nResearch only.")
    v = verify_draft(draft, flat, [], models=SCOPE_MODELS, focus_models=FOCUS_ALL)
    assert v["passed"], v
    # a genuine model-only value in unscoped text still fails
    draft2 = draft.replace("6-36 months", "0.639 overall")
    v2 = verify_draft(draft2, flat, [], models=SCOPE_MODELS, focus_models=FOCUS_ALL)
    assert not v2["passed"] and v2["unscoped_model_numbers"]


# ---------- RAG citation checks ----------

PASSAGES = {"PDQ:doc1#0": "Surgery is often the main treatment, with about "
                          "26 percent of patients alive at 5 years.",
            "PDQ:doc1#1": "Radiation therapy uses high-energy rays."}


def _ctx_draft(ctx: str) -> str:
    return _scoped_draft(
        "* cox/clinical: C 0.647\n* rsf/clinical: C 0.639\n"
        "* cox/clinical_expression: C 0.643\n* rsf/clinical_expression: C 0.632\n"
    ) + "\n\n## Context\n" + ctx


def test_unknown_citation_rejected():
    ctx = '"Surgery is often the main treatment." [PDQ:nope#9]'
    v = verify_draft(_ctx_draft(ctx), SCOPE_FLAT, [], models=SCOPE_MODELS,
                     focus_models=FOCUS_ALL, passages=PASSAGES)
    assert not v["passed"] and v["unknown_citations"]


def test_misquote_rejected():
    ctx = ('"Surgery is never the main treatment, with about 26 percent alive." '
           '[PDQ:doc1#0]')
    v = verify_draft(_ctx_draft(ctx), SCOPE_FLAT, [], models=SCOPE_MODELS,
                     focus_models=FOCUS_ALL, passages=PASSAGES)
    assert not v["passed"] and v["misquotes"]


def test_correct_quote_and_passage_numbers_pass():
    ctx = ('"Surgery is often the main treatment, with about 26 percent of '
           'patients alive at 5 years." [PDQ:doc1#0] The passage cites 26 and 5.')
    v = verify_draft(_ctx_draft(ctx), SCOPE_FLAT, [], models=SCOPE_MODELS,
                     focus_models=FOCUS_ALL, passages=PASSAGES)
    assert v["passed"], v


def test_context_numbers_must_come_from_passage():
    ctx = ('"Surgery is often the main treatment." [PDQ:doc1#0] '
           'Median survival was 48 months.')
    v = verify_draft(_ctx_draft(ctx), SCOPE_FLAT, [], models=SCOPE_MODELS,
                     focus_models=FOCUS_ALL, passages=PASSAGES)
    assert not v["passed"]
    assert any("context section" in u["context"] for u in v["unverified_numbers"])


# ---------- percentage tolerance ----------

def test_percentage_fraction_tolerance():
    # a percentage token also matches the corresponding fraction, with the
    # tolerance scaled to the fraction domain (tol/100)
    flat = {"n_patients": 501.0, "missingness.age.fraction": 0.02}
    d = ("## Cohort\n501 patients. Missingness 2% overall.\n\n"
         "## Models and metrics\nNo numeric metrics reported.\n\n"
         "## Checks and abstentions\nAll checks passed.\n\n"
         "## Limitations\nResearch only.")
    assert verify_draft(d, flat, [])["passed"]
    flat["missingness.age.fraction"] = 0.35
    assert not verify_draft(d, flat, [])["passed"]
    flat["missingness.age.fraction"] = 0.020
    d2 = d.replace("2% overall", "2.0% overall")
    assert verify_draft(d2, flat, [])["passed"]
    flat["missingness.age.fraction"] = 0.025
    assert not verify_draft(d2, flat, [])["passed"]


# ---------- analysis plan focus-model filtering ----------

def test_analysis_plan_drops_unknown_focus_models(synth_results):
    plan = ('{"focus_models": ["cox/clinical", "bogus/model"], '
            '"claims_to_make": [], "must_disclose": []}')
    rec = _agent_run(synth_results.parents[3], synth_results,
                     ["cohort text", plan, *_scripted_ok(synth_results)[2:]])
    assert rec["analysis_plan"]["focus_models"] == ["cox/clinical"]
    assert rec["analysis_plan_dropped_focus_models"] == ["bogus/model"]
    assert not rec["verification"].get("missing_focus_models")
