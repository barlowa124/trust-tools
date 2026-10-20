export interface RunSummary {
  cohort: string;
  run_id: string;
  n_patients: number | null;
  checks: { name: string; passed: boolean }[];
  abstained_models: string[];
}

export interface AgentRunSummary {
  agent_run_id: string;
  model_id: string | null;
  status: string | null;
  attempts: number;
  human_review: { decision: string; by: string } | null;
}

export interface DraftAttempt {
  attempt: number;
  text: string;
  verification?: {
    passed: boolean;
    misquotes?: { tag: string }[];
    forbidden?: string[];
    missing_sections?: string[];
    abstention_missing?: boolean;
    unverified_numbers?: string[];
  };
}

export interface AgentRun {
  agent_run_id: string;
  cohort: string;
  model_id: string;
  backend: string;
  status: string;
  seed: number | null;
  results_sha256: string;
  transcript: {
    index: number;
    prompt_sha256: string;
    model_id: string;
    elapsed_s: number;
    response?: string;
  }[];
  drafts: DraftAttempt[];
  verification?: { passed: boolean };
  final_report_sha256: string | null;
  human_review?: { decision: string; by: string; reason?: string } | null;
}

export interface Job {
  job_id: string;
  status: "running" | "done" | "failed" | string;
  detail: Record<string, unknown>;
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json() as Promise<T>;
}

export const api = {
  runs: () => get<RunSummary[]>("/runs"),
  agentRuns: (cohort: string, runId: string) =>
    get<AgentRunSummary[]>(`/runs/${cohort}/${runId}/agent`),
  agentRun: (cohort: string, runId: string, agentId: string) =>
    get<AgentRun>(`/agent/${cohort}/${runId}/${agentId}/agent_run`),
  report: (cohort: string, runId: string, agentId: string) =>
    fetch(`/agent/${cohort}/${runId}/${agentId}/report`).then((r) => {
      if (!r.ok) throw new Error(`report: ${r.status}`);
      return r.text();
    }),
  job: (id: string) => get<Job>(`/jobs/${id}`),
  trigger: (cohort: string, runId: string, backend: string) =>
    fetch(`/runs/${cohort}/${runId}/agent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ backend }),
    }).then((r) => {
      if (!r.ok) throw new Error(`trigger: ${r.status}`);
      return r.json() as Promise<{ job_id: string; status: string }>;
    }),
};
