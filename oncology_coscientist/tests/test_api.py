"""API tests on the synthetic fixture (TestClient, no server needed)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from oncocs.api.app import create_app
from tests.test_agents import (
    _agent_run,
    _scripted_ok,
)
from tests.test_agents import (
    synth_results as synth_results,  # re-export: registers the fixture
)


@pytest.fixture()
def client(synth_results):
    root = synth_results.parents[3]
    rec = _agent_run(root, synth_results, _scripted_ok(synth_results))
    app = create_app(root)
    c = TestClient(app)
    c.synth = {"root": root, "results": synth_results, "rec": rec,
               "run_id": synth_results.parent.name}
    return c


def test_list_and_get(client):
    assert "synth" in client.get("/cohorts").json()
    runs = client.get("/runs").json()
    assert any(r["run_id"] == client.synth["run_id"] for r in runs)
    detail = client.get(f"/runs/synth/{client.synth['run_id']}").json()
    assert detail["cohort"] == "synth"
    agents = client.get(f"/runs/synth/{client.synth['run_id']}/agent").json()
    assert agents[0]["agent_run_id"] == client.synth["rec"]["agent_run_id"]
    aid = agents[0]["agent_run_id"]
    rep = client.get(f"/agent/synth/{client.synth['run_id']}/{aid}/report")
    assert rep.status_code == 200 and "UNAPPROVED" in rep.text
    aj = client.get(f"/agent/synth/{client.synth['run_id']}/{aid}/agent_run")
    assert aj.status_code == 200


def test_approve_and_conflicts(client):
    aid = client.synth["rec"]["agent_run_id"]
    base = f"/agent/synth/{client.synth['run_id']}/{aid}"
    r = client.post(base + "/approve", json={"by": "tester", "note": "ok"})
    assert r.status_code == 200
    assert client.post(base + "/approve", json={"by": "x"}).status_code == 409
    assert client.post(base + "/reject",
                       json={"by": "x", "reason": "late"}).status_code == 409


def test_path_containment(client):
    # Segment escapes must 404, not resolve outside results/
    assert client.get("/runs/../cohorts/x").status_code in (404, 422)
    assert client.get("/runs/%2E%2E/%2E%2E").status_code in (404, 422)
    assert client.get("/runs/synth/../agent/x/report").status_code == 404


def test_missing_routes_404(client):
    run_id = client.synth["run_id"]
    assert client.get("/runs/synth/no-such-run").status_code == 404
    assert client.get(f"/agent/synth/{run_id}/no-such-agent/report").status_code == 404
    assert client.get(f"/agent/synth/{run_id}/no-such-agent/agent_run").status_code == 404


def test_approve_tampered_report_409(client):
    """The byte-integrity gate must hold end-to-end through the API."""
    rec = client.synth["rec"]
    run_id = client.synth["run_id"]
    report = (client.synth["results"].parent / "agent" / rec["agent_run_id"]
              / "report.md")
    # Marker stays intact; appended bytes change the file's sha256.
    report.write_text(report.read_text(encoding="utf-8") + "\ntampered line\n",
                      encoding="utf-8")
    r = client.post(f"/agent/synth/{run_id}/{rec['agent_run_id']}/approve",
                    json={"by": "tester"})
    assert r.status_code == 409


def test_reject_records_human_review(client):
    rec = client.synth["rec"]
    run_id = client.synth["run_id"]
    base = f"/agent/synth/{run_id}/{rec['agent_run_id']}"
    r = client.post(base + "/reject",
                    json={"by": "reviewer", "reason": "numbers do not check out"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    aj = client.get(base + "/agent_run").json()
    assert aj["human_review"]["decision"] == "rejected"
    assert aj["human_review"]["by"] == "reviewer"
