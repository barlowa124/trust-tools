import { useMemo, useState } from "react";
import { buildTree } from "../parse";
import type { Span, SpanNode } from "../types";

interface Props {
  spans: Span[];
}

const INDENT_PX = 20;

function attrsText(n: SpanNode): string {
  if (!n.attrs) return "";
  return Object.entries(n.attrs)
    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join("\n");
}

function Node({ n, maxMs }: { n: SpanNode; maxMs: number }) {
  const [open, setOpen] = useState(false);
  const dur = n.end_ms - n.start_ms;
  const widthPct = maxMs > 0 ? (dur / maxMs) * 100 : 0;
  const attrs = attrsText(n);
  return (
    <>
      <button className="row-head span" onClick={() => setOpen(!open)}>
        <span className="idx">{n.span_id}</span>
        <span className={`kind kind-${n.kind}`}>{n.kind}</span>
        <code className="tool">{n.name}</code>
        <span className="bar">
          <span className={`fill kind-${n.kind}`} style={{ width: `${widthPct}%` }} />
        </span>
        <span className="dur">{dur}ms</span>
      </button>
      {open && attrs && (
        <div className="row-body">
          <pre>{attrs}</pre>
        </div>
      )}
      {n.children.map((c) => (
        <div className="span-child" key={c.span_id}
          style={{ marginLeft: INDENT_PX }}>
          <Node n={c} maxMs={maxMs} />
        </div>
      ))}
    </>
  );
}

export default function SpanTree({ spans }: Props) {
  const roots = useMemo(() => buildTree(spans), [spans]);
  const maxMs = Math.max(...spans.map((s) => s.end_ms - s.start_ms), 1);
  return (
    <div>
      <div className="filters">
        <span className="count">{spans.length} spans</span>
      </div>
      {roots.map((r) => (
        <div className="row" key={r.span_id}>
          <Node n={r} maxMs={maxMs} />
        </div>
      ))}
    </div>
  );
}
