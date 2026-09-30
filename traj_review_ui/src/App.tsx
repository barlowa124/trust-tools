import { useState } from "react";
import FindingsPanel from "./components/FindingsPanel";
import SpanTree from "./components/SpanTree";
import StatsBar from "./components/StatsBar";
import Timeline from "./components/Timeline";
import { DATASETS, SPAN_DATASET } from "./data";

const SPANS_KEY = SPAN_DATASET.name;

export default function App() {
  const [name, setName] = useState(DATASETS[0].name);
  const [scrollTarget, setScrollTarget] = useState<number | null>(null);
  const spansView = name === SPANS_KEY;
  const dataset = DATASETS.find((d) => d.name === name) ?? DATASETS[0];

  const jump = (eventI: number) => {
    setScrollTarget(eventI);
    document
      .getElementById(`ev-${eventI}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  return (
    <div className="app">
      <header>
        <h1>trajectory review</h1>
        <select value={name} onChange={(e) => setName(e.target.value)}>
          {DATASETS.map((d) => (
            <option key={d.name} value={d.name}>
              {d.name} ({d.report.n_findings} findings)
            </option>
          ))}
          <option value={SPANS_KEY}>{SPANS_KEY} (span tree)</option>
        </select>
      </header>
      {spansView ? (
        <main className="full">
          <SpanTree spans={SPAN_DATASET.spans} />
        </main>
      ) : (
        <>
          <StatsBar dataset={dataset} />
          <div className="cols">
            <aside>
              <h2>findings</h2>
              <FindingsPanel findings={dataset.report.findings} onJump={jump} />
            </aside>
            <main>
              <Timeline dataset={dataset} scrollTarget={scrollTarget} />
            </main>
          </div>
        </>
      )}
    </div>
  );
}
