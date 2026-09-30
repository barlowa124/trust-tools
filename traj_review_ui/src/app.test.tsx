import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import App from "./App";
import { DATASETS } from "./data";

describe("bundled datasets", () => {
  it("parse cleanly and carry matching events", () => {
    for (const d of DATASETS) {
      expect(d.events.length).toBeGreaterThan(0);
      expect(d.report.session).toBeTruthy();
    }
  });
});

describe("App", () => {
  it("renders stats and findings for the default dataset", () => {
    render(<App />);
    expect(screen.getByText(/dazed-tachometer/)).toBeTruthy();
    expect(screen.getAllByText(/verification_claim_gap/).length).toBeGreaterThan(0);
  });

  it("switches datasets via the picker", () => {
    render(<App />);
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "unverified_claims" },
    });
    expect(screen.queryByText(/dazed-tachometer/)).toBeNull();
  });

  it("filters events by kind checkbox", () => {
    const { container } = render(<App />);
    const before = container.querySelectorAll(".row").length;
    const boxes = screen.getAllByRole("checkbox");
    fireEvent.click(boxes[1]); // tool_call off
    expect(container.querySelectorAll(".row.kind-tool_call")).toHaveLength(0);
    expect(container.querySelectorAll(".row").length).toBeLessThan(before);
  });

  it("expands a row to show body + paired result", () => {
    const { container } = render(<App />);
    const callRow = container.querySelector(".row.kind-tool_call .row-head");
    fireEvent.click(callRow!);
    expect(container.querySelector(".paired-label")?.textContent).toMatch(
      /paired tool_result #\d+/,
    );
  });
});
