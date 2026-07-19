import type { MissionSummaryData } from "../lib/summarizeFinding";

type Props = {
  summary: MissionSummaryData;
  proxyLabel?: string | null;
  progress: number;
};

export function MissionSummary({ summary, proxyLabel, progress }: Props) {
  return (
    <div className="panel mission-summary">
      <div className="mission-summary__head">
        <span
          className={`badge ${
            summary.overall === "Failed"
              ? "badge--err"
              : summary.overall === "Running"
                ? "badge--warn"
                : "badge--ok"
          }`}
        >
          {summary.overall}
        </span>
        <span className="mission-summary__target">{summary.target}</span>
        {proxyLabel && <span className="badge badge--ok">Proxy {proxyLabel}</span>}
      </div>

      <p className="mission-summary__sentence">{summary.sentence}</p>

      <div className="mission-summary__stats">
        <div className="mission-stat">
          <span className="mission-stat__value">
            {summary.openPorts.length ? summary.openPorts.join(", ") : "—"}
          </span>
          <span className="mission-stat__label">Open ports</span>
        </div>
        <div className="mission-stat">
          <span className="mission-stat__value">{summary.possibleIssues}</span>
          <span className="mission-stat__label">Possible issues</span>
        </div>
        <div className="mission-stat">
          <span className="mission-stat__value">{summary.confirmedVulns}</span>
          <span className="mission-stat__label">Confirmed vulns</span>
        </div>
        <div className="mission-stat">
          <span className="mission-stat__value">{summary.failedTools}</span>
          <span className="mission-stat__label">Failed tools</span>
        </div>
      </div>

      <div className="progress">
        <div className="progress__bar" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}
