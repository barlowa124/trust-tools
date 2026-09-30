import { timeSpan } from "../parse";
import type { Dataset } from "../types";

const KIND_ORDER = ["assistant", "tool_call", "tool_result", "user"];

export default function StatsBar({ dataset }: { dataset: Dataset }) {
  const { report, events } = dataset;
  return (
    <div className="stats">
      <span className="stat">
        session <b>{report.session}</b>
      </span>
      {KIND_ORDER.map((k) =>
        report.event_kinds[k] != null ? (
          <span className="stat" key={k}>
            {k} <b>{report.event_kinds[k]}</b>
          </span>
        ) : null,
      )}
      <span className="stat">
        findings <b className={report.n_findings ? "warn" : "ok"}>{report.n_findings}</b>
      </span>
      <span className="stat">
        span <b>{Math.round(timeSpan(events) / 60)}m</b>
      </span>
    </div>
  );
}
