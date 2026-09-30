/** Mirrors agent_trajectory_audit's JSONL event + report JSON shapes. */

export type EventKind = "assistant" | "tool_call" | "tool_result" | "user";

export interface TrajectoryEvent {
  i: number;
  kind: string;
  session: string;
  t: number;
  text?: string;
  tool?: string;
  call_id?: string;
  /** Recorded args: a string in most events, occasionally an object. */
  args?: unknown;
  v?: string;
}

export interface Finding {
  detector: string;
  event_i: number;
  summary: string;
  evidence: string[];
  severity: "low" | "medium" | "high" | string;
}

export interface AuditReport {
  session: string;
  n_events: number;
  event_kinds: Record<string, number>;
  n_findings: number;
  by_detector: Record<string, number>;
  findings: Finding[];
}

export interface Dataset {
  name: string;
  events: TrajectoryEvent[];
  report: AuditReport;
}

/** agent_observe span format (examples/agent_run.json). */

export interface Span {
  span_id: string;
  parent_id: string | null;
  name: string;
  kind: string;
  start_ms: number;
  end_ms: number;
  attrs?: Record<string, unknown>;
}

export interface SpanNode extends Span {
  children: SpanNode[];
}
