"""Read-only + human-review API over saved runs. No pipeline triggering."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from oncocs.api.schemas import ApproveRequest, RejectRequest


def create_app(root: Path) -> FastAPI:
    root = Path(root)
    app = FastAPI(title="oncocs review API")

    results_root = (root / "results").resolve()

    def _results_dir(cohort: str, run_id: str) -> Path:
        d = (results_root / cohort / run_id).resolve()
        if not d.is_relative_to(results_root) or not d.is_dir():
            raise HTTPException(404, f"run not found: {cohort}/{run_id}")
        return d

    def _agent_dir(cohort: str, run_id: str, agent_id: str) -> Path:
        d = _results_dir(cohort, run_id) / "agent" / agent_id
        if not d.is_dir():
            raise HTTPException(404, f"agent run not found: {agent_id}")
        return d

    @app.get("/cohorts")
    def cohorts():
        cdir = root / "cohorts"
        return sorted(p.stem for p in cdir.glob("*.yaml")) if cdir.is_dir() else []

    @app.get("/runs")
    def runs():
        out = []
        for rj in sorted(root.glob("results/*/*/results.json")):
            r = json.loads(rj.read_text(encoding="utf-8"))
            out.append({
                "cohort": r["cohort"], "run_id": rj.parent.name,
                "n_patients": r.get("n_patients"),
                "checks": [{"name": c["name"], "passed": c["passed"]}
                           for c in r.get("checks", [])],
                "abstained_models": [k for k, v in r.get("models", {}).items()
                                     if v.get("metrics", {}).get("abstained")],
            })
        return out

    @app.get("/runs/{cohort}/{run_id}")
    def run_detail(cohort: str, run_id: str):
        rj = _results_dir(cohort, run_id) / "results.json"
        if not rj.exists():
            raise HTTPException(404, "results.json missing")
        return json.loads(rj.read_text(encoding="utf-8"))

    @app.get("/runs/{cohort}/{run_id}/agent")
    def agent_runs(cohort: str, run_id: str):
        adir = _results_dir(cohort, run_id) / "agent"
        out = []
        if adir.is_dir():
            for aj in sorted(adir.glob("*/agent_run.json")):
                rec = json.loads(aj.read_text(encoding="utf-8"))
                out.append({"agent_run_id": rec.get("agent_run_id"),
                            "model_id": rec.get("model_id"),
                            "status": rec.get("status"),
                            "attempts": len(rec.get("drafts", [])),
                            "human_review": rec.get("human_review")})
        return out

    @app.get("/agent/{cohort}/{run_id}/{agent_id}/report")
    def agent_report(cohort: str, run_id: str, agent_id: str):
        rp = _agent_dir(cohort, run_id, agent_id) / "report.md"
        if not rp.exists():
            raise HTTPException(404, "report.md missing")
        return PlainTextResponse(rp.read_text(encoding="utf-8"))

    @app.get("/agent/{cohort}/{run_id}/{agent_id}/agent_run")
    def agent_run_json(cohort: str, run_id: str, agent_id: str):
        aj = _agent_dir(cohort, run_id, agent_id) / "agent_run.json"
        if not aj.exists():
            raise HTTPException(404, "agent_run.json missing")
        return json.loads(aj.read_text(encoding="utf-8"))

    @app.post("/agent/{cohort}/{run_id}/{agent_id}/approve")
    def agent_approve(cohort: str, run_id: str, agent_id: str, body: ApproveRequest):
        from oncocs.agents.approve import approve
        aj = _agent_dir(cohort, run_id, agent_id) / "agent_run.json"
        try:
            approve(aj, by=body.by, note=body.note)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"status": "approved", "by": body.by}

    @app.post("/agent/{cohort}/{run_id}/{agent_id}/reject")
    def agent_reject(cohort: str, run_id: str, agent_id: str, body: RejectRequest):
        from oncocs.agents.approve import reject
        aj = _agent_dir(cohort, run_id, agent_id) / "agent_run.json"
        try:
            reject(aj, by=body.by, reason=body.reason)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"status": "rejected", "by": body.by}

    return app
