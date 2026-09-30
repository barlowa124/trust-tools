/** Pure parsing helpers — kept framework-free so vitest can exercise
 * them without a DOM. */

import type { AuditReport, TrajectoryEvent } from "./types";

export function parseTrajectoryJsonl(raw: string): TrajectoryEvent[] {
  return raw
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l, line) => {
      try {
        return JSON.parse(l) as TrajectoryEvent;
      } catch {
        throw new Error(`bad JSONL at line ${line + 1}`);
      }
    });
}

export function parseReport(raw: string): AuditReport {
  return JSON.parse(raw) as AuditReport;
}

/** call_id links a tool_call to its tool_result. */
export function pairToolResults(
  events: TrajectoryEvent[],
): Map<string, TrajectoryEvent> {
  const byCall = new Map<string, TrajectoryEvent>();
  for (const e of events)
    if (e.kind === "tool_result" && e.call_id) byCall.set(e.call_id, e);
  return byCall;
}

/** Findings indexed by the event they point at. */
export function findingsByEvent(
  report: AuditReport,
): Map<number, typeof report.findings> {
  const m = new Map<number, AuditReport["findings"]>();
  for (const f of report.findings) {
    const arr = m.get(f.event_i) ?? [];
    arr.push(f);
    m.set(f.event_i, arr);
  }
  return m;
}

export function timeSpan(events: TrajectoryEvent[]): number {
  if (events.length < 2) return 0;
  const ts = events.map((e) => e.t).filter((t) => t != null);
  return Math.max(...ts) - Math.min(...ts);
}

export function preview(s: string | undefined, n = 160): string {
  if (!s) return "";
  const flat = s.replace(/\s+/g, " ").trim();
  return flat.length > n ? flat.slice(0, n) + "…" : flat;
}
