"""FastAPI wiring for Service. Optional dependency: `pip install .[api]`.

Endpoints:
  POST /infer        {"prompt": "..."} -> response record (hash-bound)
  GET  /report       throughput + shadow agreement
  GET  /verify       chain check over all response records so far
"""

from __future__ import annotations


def build_app(service, name: str = "modelserve"):
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI(title=name)

    class InferRequest(BaseModel):
        prompt: str
        timeout_s: float = 30.0

    @app.post("/infer")
    def infer(req: InferRequest):
        return service.infer(req.prompt, timeout_s=req.timeout_s)

    @app.get("/report")
    def report():
        return service.report()

    @app.get("/verify")
    def verify():
        problems = service.check_chain()
        return {"records": len(service.records),
                "problems": problems, "ok": not problems}

    return app
