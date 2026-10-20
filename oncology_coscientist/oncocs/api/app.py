"""Review API over saved runs plus agent-run triggering.

Read endpoints serve the Postgres mirror when DATABASE_URL is set
(deployed mode) and the results/ filesystem otherwise (local mode).
POST /runs/{cohort}/{run_id}/agent launches a drafting pass in a
background thread — the LLM backend comes from the environment, so the
model can live anywhere (Colab, a tunneled server, scripted-demo for
offline checks).
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from oncocs.api.schemas import AgentRunRequest, ApproveRequest, RejectRequest
from oncocs.store import Store


def _env_backend(backend_name: str, seed: int | None = None):
    """Backend for a triggered run. 'endpoint' reads ONCOCS_LLM_* env;
    'ollama' uses the local server; 'scripted-demo' never touches a
    network — it is what tests and offline smoke checks use."""
    if backend_name == "endpoint":
        from oncocs.llm.endpoint import EndpointBackend
        return EndpointBackend()
    if backend_name == "ollama":
        import os

        from oncocs.llm.ollama import OllamaBackend
        return OllamaBackend(model=os.environ.get("ONCOCS_LLM_MODEL",
                                                  "gemma3:4b"))
    if backend_name == "scripted-demo":
        return None  # built per-results inside the trigger
    raise ValueError(f"unknown backend {backend_name!r}")


def create_app(root: Path) -> FastAPI:
    root = Path(root)
    app = FastAPI(title="oncocs review API")
    store = Store.from_env()
    app.state.store = store
    app.state.jobs = {}          # job_id -> dict, in-memory fallback

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

    def _run_id_of(results_path: Path) -> str:
        return results_path.parent.name

    def _backend_for_request(body: AgentRunRequest, results: dict):
        if body.backend == "scripted-demo":
            from oncocs.agents.demo import demo_backend
            from oncocs.config import load_cohort
            from oncocs.splits import load_split
            split = load_split(load_cohort(results["cohort"], root), root)
            return demo_backend(results, split)
        return _env_backend(body.backend, body.seed)

    def _do_agent_run(cohort: str, results_path: Path,
                      body: AgentRunRequest, job_id: str):
        try:
            results = json.loads(results_path.read_text(encoding="utf-8"))
            backend = _backend_for_request(body, results)
            from oncocs.agents.graph import run_agent
            record = run_agent(cohort, results_path, backend,
                               body.seed, root)
            record["run_id"] = _run_id_of(results_path)
            if store.enabled:
                store.upsert_agent_run(record)
                store.finish_job(job_id, "done",
                                 {"agent_run_id": record["agent_run_id"],
                                  "status": record.get("status")})
            app.state.jobs[job_id] = {
                "job_id": job_id, "kind": "agent_run", "status": "done",
                "detail": {"agent_run_id": record["agent_run_id"],
                           "status": record.get("status")}}
        except Exception as exc:  # surfaced via job status, not the socket
            if store.enabled:
                store.finish_job(job_id, "failed", {"error": str(exc)})
            app.state.jobs[job_id] = {
                "job_id": job_id, "kind": "agent_run", "status": "failed",
                "detail": {"error": str(exc)}}

    @app.post("/runs/{cohort}/{run_id}/agent", status_code=202)
    def trigger_agent(cohort: str, run_id: str, body: AgentRunRequest):
        rdir = _results_dir(cohort, run_id)
        results_path = rdir / "results.json"
        if not results_path.exists():
            raise HTTPException(404, "results.json missing")
        job_id = uuid.uuid4().hex[:12]
        if store.enabled:
            store.start_job(job_id, "agent_run",
                            {"cohort": cohort, "run_id": run_id,
                             "backend": body.backend})
        app.state.jobs[job_id] = {
            "job_id": job_id, "kind": "agent_run", "status": "running",
            "detail": {"cohort": cohort, "run_id": run_id,
                       "backend": body.backend}}
        t = threading.Thread(target=_do_agent_run,
                             args=(cohort, results_path, body, job_id),
                             daemon=True)
        t.start()
        return {"job_id": job_id, "status": "running"}

    @app.get("/jobs/{job_id}")
    def job_status(job_id: str):
        if store.enabled:
            job = store.get_job(job_id)
            if job:
                return job
        job = app.state.jobs.get(job_id)
        if not job:
            raise HTTPException(404, f"job not found: {job_id}")
        return job

    @app.get("/runs/{cohort}/{run_id}")
    def run_detail(cohort: str, run_id: str):
        rj = _results_dir(cohort, run_id) / "results.json"
        if not rj.exists():
            raise HTTPException(404, "results.json missing")
        return json.loads(rj.read_text(encoding="utf-8"))

    @app.get("/runs/{cohort}/{run_id}/agent")
    def agent_runs(cohort: str, run_id: str):
        if store.enabled:
            return store.list_agent_runs(cohort=cohort, run_id=run_id)
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
        if store.enabled:
            rec = store.get_agent_run(agent_id)
            if rec is not None:
                return rec
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
        if store.enabled:
            rec = json.loads(aj.read_text(encoding="utf-8"))
            rec["run_id"] = run_id
            store.upsert_agent_run(rec)
        return {"status": "approved", "by": body.by}

    @app.post("/agent/{cohort}/{run_id}/{agent_id}/reject")
    def agent_reject(cohort: str, run_id: str, agent_id: str, body: RejectRequest):
        from oncocs.agents.approve import reject
        aj = _agent_dir(cohort, run_id, agent_id) / "agent_run.json"
        try:
            reject(aj, by=body.by, reason=body.reason)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        if store.enabled:
            rec = json.loads(aj.read_text(encoding="utf-8"))
            rec["run_id"] = run_id
            store.upsert_agent_run(rec)
        return {"status": "rejected", "by": body.by}

    web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if web_dist.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/ui", StaticFiles(directory=web_dist, html=True),
                  name="ui")

    return app
