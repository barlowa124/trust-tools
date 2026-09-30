import { useRef, useState } from "react";
import FindingsPanel from "./components/FindingsPanel";
import StatsBar from "./components/StatsBar";
import Timeline from "./components/Timeline";
import { DATASETS } from "./data";

export default function App() {
  const [name, setName] = useState(DATASETS[0].name);
  const [scrollTarget, setScrollTarget] = useState<number | null>(null);
  const timelineRef = useRef<HTMLDivElement>(null);
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
        </select>
      </header>
      <StatsBar dataset={dataset} />
      <div className="cols">
        <aside>
          <h2>findings</h2>
          <FindingsPanel findings={dataset.report.findings} onJump={jump} />
        </aside>
        <main>
          <Timeline
            ref={timelineRef}
            dataset={dataset}
            scrollTarget={scrollTarget}
          />
        </main>
      </div>
    </div>
  );
}
