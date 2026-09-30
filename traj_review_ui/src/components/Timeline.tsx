import { forwardRef, useMemo, useState } from "react";
import { findingsByEvent, pairToolResults } from "../parse";
import type { Dataset } from "../types";
import EventRow from "./EventRow";

const KINDS = ["assistant", "tool_call", "tool_result", "user"];

interface Props {
  dataset: Dataset;
  scrollTarget: number | null;
}

const Timeline = forwardRef<HTMLDivElement, Props>(function Timeline(
  { dataset, scrollTarget },
  ref,
) {
  const [kinds, setKinds] = useState<Set<string>>(new Set(KINDS));
  const [query, setQuery] = useState("");

  const results = useMemo(
    () => pairToolResults(dataset.events),
    [dataset],
  );
  const byEvent = useMemo(
    () => findingsByEvent(dataset.report),
    [dataset],
  );

  const visible = dataset.events.filter((e) => {
    if (!kinds.has(e.kind)) return false;
    if (query) {
      const args = typeof e.args === "string" ? e.args : JSON.stringify(e.args ?? "");
      const hay = `${e.text ?? ""} ${args} ${e.tool ?? ""}`.toLowerCase();
      if (!hay.includes(query.toLowerCase())) return false;
    }
    return true;
  });

  const toggle = (k: string) => {
    const next = new Set(kinds);
    if (next.has(k)) next.delete(k);
    else next.add(k);
    setKinds(next);
  };

  return (
    <div ref={ref}>
      <div className="filters">
        {KINDS.map((k) => (
          <label key={k} className={kinds.has(k) ? "on" : ""}>
            <input
              type="checkbox"
              checked={kinds.has(k)}
              onChange={() => toggle(k)}
            />
            {k}
          </label>
        ))}
        <input
          className="search"
          placeholder="filter text…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="count">
          {visible.length}/{dataset.events.length}
        </span>
      </div>
      {visible.map((e) => (
        <EventRow
          key={e.i}
          event={e}
          result={e.kind === "tool_call" && e.call_id ? results.get(e.call_id) : undefined}
          findings={byEvent.get(e.i)}
          highlight={scrollTarget === e.i}
        />
      ))}
      {visible.length === 0 && <p className="empty">no events match</p>}
    </div>
  );
});

export default Timeline;
