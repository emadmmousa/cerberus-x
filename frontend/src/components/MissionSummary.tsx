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

      {(summary.impactProven ||
        summary.postExSucceeded > 0 ||
        summary.postExFailed > 0) && (
        <p className="mission-summary__exploit-line">
          {summary.impactProven &&
            `Access proven (${summary.sessions} session${summary.sessions === 1 ? "" : "s"})`}
          {summary.impactProven &&
            (summary.postExSucceeded > 0 || summary.postExFailed > 0) &&
            " · "}
          {(summary.postExSucceeded > 0 || summary.postExFailed > 0) &&
            `Post-ex: ${summary.postExSucceeded} ok, ${summary.postExFailed} failed`}
        </p>
      )}

      <div className="mission-summary__stats">
        <div className="mission-stat">
          <span className="mission-stat__value">
            {summary.openPorts.length ? summary.openPorts.join(", ") : "—"}
          </span>
          <span className="mission-stat__label">Ports</span>
        </div>
        <div className="mission-stat">
          <span className="mission-stat__value">{summary.possibleIssues}</span>
          <span className="mission-stat__label">Issues</span>
        </div>
        <div className="mission-stat">
          <span className="mission-stat__value">{summary.confirmedVulns}</span>
          <span className="mission-stat__label">Confirmed</span>
        </div>
        <div className="mission-stat">
          <span className="mission-stat__value">{summary.failedTools}</span>
          <span className="mission-stat__label">Failed</span>
        </div>
      </div>

      <div className="progress">
        <div className="progress__bar" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}
