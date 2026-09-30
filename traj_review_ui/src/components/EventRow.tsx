import { useState } from "react";
import { preview } from "../parse";
import type { Finding, TrajectoryEvent } from "../types";

interface Props {
  event: TrajectoryEvent;
  result?: TrajectoryEvent; // paired tool_result for tool_call rows
  findings?: Finding[];
  highlight: boolean;
}

function body(e: TrajectoryEvent): string {
  if (e.text) return e.text;
  if (e.args != null)
    return typeof e.args === "string" ? e.args : JSON.stringify(e.args, null, 1);
  return "";
}

export default function EventRow({ event, result, findings, highlight }: Props) {
  const [open, setOpen] = useState(false);
  const flagged = (findings?.length ?? 0) > 0;

  return (
    <div
      id={`ev-${event.i}`}
      className={`row kind-${event.kind} ${flagged ? "flagged" : ""} ${highlight ? "highlight" : ""}`}
    >
      <button className="row-head" onClick={() => setOpen(!open)}>
        <span className="idx">#{event.i}</span>
        <span className={`kind kind-${event.kind}`}>{event.kind}</span>
        {event.tool && <code className="tool">{event.tool}</code>}
        <span className="preview">{preview(body(event))}</span>
        {flagged && <span className="flag-dot" title="finding points here" />}
      </button>
      {open && (
        <div className="row-body">
          <pre>{body(event) || "(empty)"}</pre>
          {result && (
            <>
              <div className="paired-label">paired tool_result #{result.i}</div>
              <pre>{preview(body(result), 400)}</pre>
            </>
          )}
          {findings?.map((f, i) => (
            <p className={`finding-inline sev-${f.severity}`} key={i}>
              {f.severity}: {f.summary}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
