import { describe, expect, it } from "vitest";
import {
  findingsByEvent,
  pairToolResults,
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
