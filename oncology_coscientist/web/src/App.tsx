import { useCallback, useEffect, useState } from "react";
import { api, AgentRun, AgentRunSummary, RunSummary } from "./api";

type Route =
  | { view: "runs" }
  | { view: "run"; cohort: string; runId: string }
  | { view: "agent"; cohort: string; runId: string; agentId: string };

function StatusBadge({ status }: { status: string | null | undefined }) {
  const s = status ?? "unknown";
  const cls =
    s === "approved"
      ? "approved"
      : s === "rejected" || s === "failed"
        ? "rejected"
        : "pending";
  return <span className={`badge ${cls}`}>{s}</span>;
}

function RunsView({ go }: { go: (r: Route) => void }) {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api.runs().then(setRuns).catch((e) => setErr(String(e)));
  }, []);
  if (err) return <p className="fail">{err}</p>;
  if (!runs) return <p className="muted">loading…</p>;
  return (
    <table>
      <thead>
        <tr>
          <th>cohort</th>
          <th>run</th>
          <th>patients</th>
          <th>checks</th>
          <th>abstained</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => {
          const failed = r.checks.filter((c) => !c.passed).length;
          return (
            <tr
              key={`${r.cohort}/${r.run_id}`}
              className="clickable"
              onClick={() =>
                go({ view: "run", cohort: r.cohort, runId: r.run_id })
              }
            >
              <td>{r.cohort}</td>
              <td className="muted">{r.run_id}</td>
              <td>{r.n_patients ?? "—"}</td>
              <td>
                {failed === 0 ? (
                  <span className="pass">{r.checks.length} passed</span>
                ) : (
                  <span className="fail">
                    {failed}/{r.checks.length} failed
                  </span>
                )}
              </td>
              <td className={r.abstained_models.length ? "warn" : ""}>
                {r.abstained_models.length
                  ? r.abstained_models.join(", ")
                  : "—"}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function RunView({
  cohort,
  runId,
  go,
}: {
  cohort: string;
  runId: string;
  go: (r: Route) => void;
}) {
  const [agents, setAgents] = useState<AgentRunSummary[] | null>(null);
  const [job, setJob] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api.agentRuns(cohort, runId).then(setAgents).catch((e) => setErr(String(e)));
  }, [cohort, runId]);

  useEffect(refresh, [refresh]);

  useEffect(() => {
    if (!job) return;
    const t = setInterval(() => {
      api
        .job(job)
        .then((j) => {
          setJobStatus(j.status);
          if (j.status !== "running") {
            setJob(null);
            refresh();
            clearInterval(t);
          }
        })
        .catch(() => clearInterval(t));
    }, 2000);
    return () => clearInterval(t);
  }, [job, refresh]);

  const trigger = (backend: string) => {
    setErr(null);
    api
      .trigger(cohort, runId, backend)
      .then((r) => {
        setJob(r.job_id);
        setJobStatus("running");
      })
      .catch((e) => setErr(String(e)));
  };

  if (err) return <p className="fail">{err}</p>;
  if (!agents) return <p className="muted">loading…</p>;
  return (
    <>
      <h2>
        {cohort} <span className="muted">/ {runId}</span>
      </h2>
      <p>
        <button onClick={() => trigger("endpoint")} disabled={!!job}>
          new agent run (endpoint)
        </button>{" "}
        <button onClick={() => trigger("scripted-demo")} disabled={!!job}>
          new agent run (scripted demo)
        </button>{" "}
        {jobStatus && <span className="muted">job {job}: {jobStatus}</span>}
      </p>
      <table>
        <thead>
          <tr>
            <th>agent run</th>
            <th>model</th>
            <th>status</th>
            <th>attempts</th>
            <th>review</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((a) => (
            <tr
              key={a.agent_run_id}
              className="clickable"
              onClick={() =>
                go({
                  view: "agent",
                  cohort,
                  runId,
                  agentId: a.agent_run_id,
                })
              }
            >
              <td className="muted">{a.agent_run_id}</td>
              <td>{a.model_id ?? "—"}</td>
              <td>
                <StatusBadge status={a.status} />
              </td>
              <td>{a.attempts}</td>
              <td>
                {a.human_review ? (
                  <StatusBadge status={a.human_review.decision} />
                ) : (
                  <span className="muted">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {agents.length === 0 && (
        <p className="muted">no agent runs yet — trigger one above</p>
      )}
    </>
  );
}

function AgentView({
  cohort,
  runId,
  agentId,
}: {
  cohort: string;
  runId: string;
  agentId: string;
}) {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [report, setReport] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api.agentRun(cohort, runId, agentId).then(setRun).catch((e) => setErr(String(e)));
    api.report(cohort, runId, agentId).then(setReport).catch(() => setReport(null));
  }, [cohort, runId, agentId]);
  if (err) return <p className="fail">{err}</p>;
  if (!run) return <p className="muted">loading…</p>;
  return (
    <>
      <h2>
        agent run <span className="muted">{run.agent_run_id}</span>
      </h2>
      <div className="card">
        <StatusBadge status={run.status} />{" "}
        <span className="muted">
          {run.model_id} via {run.backend} · seed {run.seed ?? "—"} · results{" "}
          {run.results_sha256.slice(0, 12)}…
        </span>
      </div>

      <h2>draft attempts ({run.drafts.length})</h2>
      {run.drafts.map((d) => {
        const v = d.verification;
        const findings: string[] = [];
        if (v) {
          (v.misquotes ?? []).forEach((m) => findings.push(`misquote ${m.tag}`));
          (v.forbidden ?? []).forEach((f) => findings.push(`forbidden: ${f}`));
          (v.missing_sections ?? []).forEach((s) =>
            findings.push(`missing section: ${s}`)
          );
          (v.unverified_numbers ?? []).forEach((n) =>
            findings.push(`unverified: ${n}`)
          );
          if (v.abstention_missing)
            findings.push("abstention not disclosed");
        }
        return (
          <div className="card" key={d.attempt}>
            <span className={v?.passed ? "pass" : "fail"}>
              attempt {d.attempt}: {v ? (v.passed ? "passed" : "rejected") : "?"}
            </span>{" "}
            <span className="muted">{findings.join("; ")}</span>
            <pre>{d.text.slice(0, 2000)}</pre>
          </div>
        );
      })}

      <h2>transcript ({run.transcript.length} calls)</h2>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>prompt sha</th>
            <th>model</th>
            <th>elapsed</th>
          </tr>
        </thead>
        <tbody>
          {run.transcript.map((t) => (
            <tr key={t.index}>
              <td className="muted">{t.index}</td>
              <td className="muted">{t.prompt_sha256.slice(0, 16)}…</td>
              <td>{t.model_id}</td>
              <td>{t.elapsed_s}s</td>
            </tr>
          ))}
        </tbody>
      </table>

      {report && (
        <>
          <h2>report.md</h2>
          <pre>{report}</pre>
        </>
      )}
    </>
  );
}

export default function App() {
  const [route, setRoute] = useState<Route>({ view: "runs" });
  return (
    <>
      <h1>oncocs — verified reporting</h1>
      <p className="nav">
        {route.view !== "runs" && (
          <a href="#" onClick={() => setRoute({ view: "runs" })}>
            ← runs
          </a>
        )}{" "}
        {route.view === "agent" && (
          <a
            href="#"
            onClick={() =>
              setRoute({
                view: "run",
                cohort: route.cohort,
                runId: route.runId,
              })
            }
          >
            ← agent runs
          </a>
        )}
      </p>
      {route.view === "runs" && <RunsView go={setRoute} />}
      {route.view === "run" && (
        <RunView cohort={route.cohort} runId={route.runId} go={setRoute} />
      )}
      {route.view === "agent" && (
        <AgentView
          cohort={route.cohort}
          runId={route.runId}
          agentId={route.agentId}
        />
      )}
    </>
  );
}
