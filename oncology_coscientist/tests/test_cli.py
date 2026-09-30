"""CLI entry-point tests on the synthetic fixture."""
from __future__ import annotations

import json
from pathlib import Path

from oncocs.cli import main
from tests.test_agents import (
    synth_results as synth_results,  # re-export: registers the fixture
)


def _argv(root, *rest):
    return ["--data-dir", str(root), *rest]


def test_verify_pass_and_tamper_fail(synth_results):
    root = synth_results.parents[3]
    assert main(_argv(root, "verify", str(synth_results))) == 0

    tampered = json.loads(synth_results.read_text())
    tampered["n_patients"] += 1
    synth_results.write_text(json.dumps(tampered, indent=2))
    assert main(_argv(root, "verify", str(synth_results))) == 1


def test_qc_and_agent_summarize(synth_results):
    from tests.test_agents import _agent_run, _scripted_ok

    root = synth_results.parents[3]
    assert main(_argv(root, "qc", "--cohort", "synth")) == 0

    rec = _agent_run(root, synth_results, _scripted_ok(synth_results))
    assert main(_argv(root, "agent", "summarize")) == 0
    out = root / "results" / "agent_model_comparison.json"
    runs = json.loads(out.read_text())["runs"]
    assert any(r["agent_run_id"] == rec["agent_run_id"] for r in runs)


def test_agent_replay_and_cli_approve_reject(synth_results):
    from tests.test_agents import _agent_run, _run_path, _scripted_ok

    root = synth_results.parents[3]
    rec = _agent_run(root, synth_results, _scripted_ok(synth_results))
    run_path = _run_path(synth_results, rec)

    assert main(_argv(root, "agent", "replay", str(run_path))) == 0
    assert main(_argv(root, "approve", str(run_path), "--by", "cli-tester")) == 0
    record = json.loads(run_path.read_text())
    assert record["approval"]["by"] == "cli-tester"
    # second decision on the same run must fail closed
    assert main(_argv(root, "reject", str(run_path),
                      "--by", "x", "--reason", "late")) == 1


def test_rag_retrieve_modes():
    from oncocs.rag.retrieve import retrieve

    q = "non-small cell lung cancer overall survival treatment"
    bm = retrieve(q, top_k=5, mode="bm25")
    tf = retrieve(q, top_k=5, mode="tfidf")
    assert bm and tf
    assert all(t.startswith("PDQ:") for t in bm)
    assert all(t.startswith("PDQ:") for t in tf)


def test_rag_retrieve_unknown_mode_and_embed_guard():
    import pytest

    from oncocs.rag.retrieve import retrieve
    with pytest.raises(ValueError):
        retrieve("x", mode="bogus")
    with pytest.raises(RuntimeError, match="vector-db-mcp"):
        retrieve("x", mode="embed")


def test_rag_compare_writes_artifact(synth_root, tmp_path):
    import shutil

    # rag/corpus lives at repo root; copy it into the fixture root
    corpus_src = Path(__file__).resolve().parents[1] / "rag" / "corpus"
    dst = synth_root / "rag" / "corpus"
    dst.mkdir(parents=True)
    for f in corpus_src.glob("*.txt"):
        shutil.copy(f, dst)
    main(_argv(synth_root, "rag", "compare",
               "--queries", "lung cancer survival;brca treatment",
               "--modes", "bm25,tfidf"))
    out = json.loads((synth_root / "results" / "rag_mode_comparison.json")
                     .read_text())
    assert len(out["per_query"]) == 2
    assert "tfidf" in out["per_query"][0]["overlap_with_first_mode"]
