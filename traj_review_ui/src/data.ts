/** Bundled datasets — real committed artifacts from
 * agent_trajectory_audit/examples/, imported as raw text so the app is a
 * static demo with no backend. Add a dataset by dropping its
 * trajectory/report pair here and extending DATASETS. */

import { parseReport, parseSpans, parseTrajectoryJsonl } from "./parse";
import type { Dataset, Span } from "./types";

import trajDashboard from "./sample/dashboard-build-window.jsonl?raw";
import repDashboard from "./sample/dashboard-build-window.json?raw";
import trajClean from "./sample/clean_run.jsonl?raw";
import repClean from "./sample/clean_run.json?raw";
import trajDrift from "./sample/drift_and_scope.jsonl?raw";
import repDrift from "./sample/drift_and_scope.json?raw";
import trajClaims from "./sample/unverified_claims.jsonl?raw";
import repClaims from "./sample/unverified_claims.json?raw";
import agentRun from "./sample/agent_run.json?raw";

/** agent_observe span trace — a different artifact shape, rendered as a
 * span tree rather than the event timeline. */
export const SPAN_DATASET: { name: string; spans: Span[] } = {
  name: "agent_run (spans)",
  spans: parseSpans(agentRun),
};

export const DATASETS: Dataset[] = [
  {
    name: "dashboard-build-window",
    events: parseTrajectoryJsonl(trajDashboard),
    report: parseReport(repDashboard),
  },
  {
    name: "unverified_claims",
    events: parseTrajectoryJsonl(trajClaims),
    report: parseReport(repClaims),
  },
  {
    name: "drift_and_scope",
    events: parseTrajectoryJsonl(trajDrift),
    report: parseReport(repDrift),
  },
  {
    name: "clean_run",
    events: parseTrajectoryJsonl(trajClean),
    report: parseReport(repClean),
  },
];
