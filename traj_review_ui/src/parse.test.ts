import { describe, expect, it } from "vitest";
import {
  buildTree,
  findingsByEvent,
  pairToolResults,
  parseSpans,
  parseTrajectoryJsonl,
  preview,
  timeSpan,
} from "./parse";

const LINES = [
  { i: 0, kind: "assistant", session: "s", t: 100, text: "plan" },
  { i: 1, kind: "tool_call", session: "s", t: 110, tool: "write", call_id: "c1", args: "{}" },
  { i: 2, kind: "tool_result", session: "s", t: 115, tool: "write", call_id: "c1", args: "{ok}" },
  { i: 3, kind: "tool_call", session: "s", t: 120, tool: "read", call_id: "c2", args: "{}" },
];

const RAW = LINES.map((l) => JSON.stringify(l)).join("\n") + "\n";

describe("parseTrajectoryJsonl", () => {
  it("parses every non-blank line", () => {
    const evs = parseTrajectoryJsonl(RAW);
    expect(evs).toHaveLength(4);
    expect(evs[1].tool).toBe("write");
  });
  it("throws with the offending line number", () => {
    expect(() => parseTrajectoryJsonl("{}\nnot json\n")).toThrow("line 2");
  });
  it("tolerates blank lines and trailing newline", () => {
    expect(parseTrajectoryJsonl("\n" + LINES.map((l) => JSON.stringify(l)).join("\n\n") + "\n\n"))
      .toHaveLength(4);
  });
});

describe("pairToolResults", () => {
  it("links results to their call", () => {
    const m = pairToolResults(parseTrajectoryJsonl(RAW));
    expect(m.get("c1")?.i).toBe(2);
    expect(m.has("c2")).toBe(false); // call without a result
  });
});

describe("findingsByEvent", () => {
  it("groups multiple findings on one event", () => {
    const m = findingsByEvent({
      session: "s", n_events: 4, event_kinds: {}, n_findings: 2,
      by_detector: {},
      findings: [
        { detector: "a", event_i: 1, summary: "x", evidence: [], severity: "low" },
        { detector: "b", event_i: 1, summary: "y", evidence: [], severity: "high" },
      ],
    });
    expect(m.get(1)).toHaveLength(2);
    expect(m.has(0)).toBe(false);
  });
});

describe("spans", () => {
  const SPANS = [
    { span_id: "s1", parent_id: null, name: "run", kind: "agent",
      start_ms: 0, end_ms: 100 },
    { span_id: "s2", parent_id: "s1", name: "plan", kind: "llm",
      start_ms: 0, end_ms: 40 },
    { span_id: "s3", parent_id: "s1", name: "write", kind: "tool_call",
      start_ms: 50, end_ms: 90 },
  ];

  it("parses a span array", () => {
    expect(parseSpans(JSON.stringify(SPANS))).toHaveLength(3);
    expect(() => parseSpans("{}")).toThrow("array");
  });

  it("buildTree nests children in start order", () => {
    const roots = buildTree(parseSpans(JSON.stringify(SPANS)));
    expect(roots).toHaveLength(1);
    expect(roots[0].children.map((c) => c.span_id)).toEqual(["s2", "s3"]);
  });

  it("orphans become roots", () => {
    const roots = buildTree([
      { ...SPANS[0] },
      { ...SPANS[1], parent_id: "missing" },
    ]);
    expect(roots).toHaveLength(2);
  });
});

describe("timeSpan / preview", () => {
  it("spans first to last timestamp", () => {
    expect(timeSpan(parseTrajectoryJsonl(RAW))).toBe(20);
  });
  it("truncates with ellipsis", () => {
    expect(preview("  a  b   ".repeat(30), 20)).toMatch(/…$/);
    expect(preview("short")).toBe("short");
    expect(preview(undefined)).toBe("");
  });
});
