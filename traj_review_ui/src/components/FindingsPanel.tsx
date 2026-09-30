import type { Finding } from "../types";

interface Props {
  findings: Finding[];
  onJump: (eventI: number) => void;
}

export default function FindingsPanel({ findings, onJump }: Props) {
  if (!findings.length)
    return <p className="empty">no findings — detectors found nothing anomalous</p>;
  return (
    <div className="findings">
      {findings.map((f, idx) => (
        <div className={`finding sev-${f.severity}`} key={idx}>
          <div className="finding-head">
            <span className={`badge sev-${f.severity}`}>{f.severity}</span>
            <code>{f.detector}</code>
            <button onClick={() => onJump(f.event_i)} title="jump to event">
              event {f.event_i}
            </button>
          </div>
          <p>{f.summary}</p>
          {f.evidence.length > 0 && (
            <details>
              <summary>evidence ({f.evidence.length})</summary>
              {f.evidence.map((e, i) => (
                <pre key={i}>{e}</pre>
              ))}
            </details>
          )}
        </div>
      ))}
    </div>
  );
}
