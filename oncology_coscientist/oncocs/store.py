"""Postgres mirror of agent-run records for the deployed API.

The filesystem under results/ stays canonical — records are written by
run_agent before any store call. The store is the deployment read
model: /runs and /agent endpoints serve it when DATABASE_URL is set,
and the trigger endpoint registers job state there.

Requires psycopg (optional "deploy" extra). Everything degrades to the
filesystem implementation when the env var or driver is absent, so the
package stays stdlib+requests installable without Postgres.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_runs (
    agent_run_id TEXT PRIMARY KEY,
    cohort TEXT NOT NULL,
    run_id TEXT NOT NULL,
    model_id TEXT,
    backend TEXT,
    status TEXT,
    record JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);
"""


def _connect(dsn: str):
    import psycopg
    return psycopg.connect(dsn)


class Store:
    """None when Postgres is not configured — callers fall back to
    filesystem reads. `enabled` keeps the check cheap and explicit."""

    enabled = False

    @staticmethod
    def from_env(dsn: str | None = None) -> Store:
        dsn = dsn if dsn is not None else os.environ.get("DATABASE_URL")
        if not dsn:
            return Store()
        try:
            conn = _connect(dsn)
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
            conn.commit()
            conn.close()
        except ImportError:
            return Store()
        return PgStore(dsn)


class PgStore(Store):
    enabled = True

    def __init__(self, dsn: str):
        self.dsn = dsn

    def upsert_agent_run(self, record: dict) -> None:
        """Mirror one agent_run.json record. Review state is part of the
        record, so approve/reject re-upserts the whole thing."""
        with _connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO agent_runs (agent_run_id, cohort, run_id,"
                    " model_id, backend, status, record)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)"
                    " ON CONFLICT (agent_run_id) DO UPDATE SET"
                    " model_id = EXCLUDED.model_id,"
                    " backend = EXCLUDED.backend,"
                    " status = EXCLUDED.status,"
                    " record = EXCLUDED.record",
                    (record["agent_run_id"], record["cohort"],
                     record.get("run_id", ""),
                     record.get("model_id"), record.get("backend"),
                     record.get("status"), json.dumps(record, default=str)))

    def list_agent_runs(self, cohort: str | None = None,
                        run_id: str | None = None) -> list[dict]:
        q = ("SELECT agent_run_id, cohort, run_id, model_id, status,"
             " record->'human_review' AS human_review,"
             " jsonb_array_length(COALESCE(record->'drafts','[]'::jsonb))"
             " AS attempts FROM agent_runs")
        cond, params = [], []
        if cohort:
            cond.append("cohort = %s")
            params.append(cohort)
        if run_id:
            cond.append("run_id = %s")
            params.append(run_id)
        if cond:
            q += " WHERE " + " AND ".join(cond)
        q += " ORDER BY created_at DESC"
        with _connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(q, params)
                return [{"agent_run_id": r[0], "cohort": r[1],
                         "run_id": r[2], "model_id": r[3], "status": r[4],
                         "human_review": r[5], "attempts": r[6]}
                        for r in cur.fetchall()]

    def get_agent_run(self, agent_run_id: str) -> dict | None:
        with _connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT record FROM agent_runs"
                            " WHERE agent_run_id = %s", (agent_run_id,))
                row = cur.fetchone()
        if not row:
            return None
        # psycopg3 decodes jsonb to dict; a str means a driver that
        # returned raw text.
        rec = row[0]
        return rec if isinstance(rec, dict) else json.loads(rec)

    def start_job(self, job_id: str, kind: str, detail: dict) -> None:
        with _connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO jobs (job_id, kind, status, detail)"
                    " VALUES (%s, %s, 'running', %s::jsonb)",
                    (job_id, kind, json.dumps(detail, default=str)))

    def finish_job(self, job_id: str, status: str,
                   detail: dict | None = None) -> None:
        with _connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET status = %s, detail = %s::jsonb,"
                    " finished_at = %s WHERE job_id = %s",
                    (status, json.dumps(detail or {}, default=str),
                     datetime.now(UTC), job_id))

    def get_job(self, job_id: str) -> dict | None:
        with _connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT job_id, kind, status, detail,"
                            " created_at, finished_at FROM jobs"
                            " WHERE job_id = %s", (job_id,))
                row = cur.fetchone()
        if not row:
            return None
        return {"job_id": row[0], "kind": row[1], "status": row[2],
                "detail": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
                "finished_at": row[5].isoformat() if row[5] else None}
