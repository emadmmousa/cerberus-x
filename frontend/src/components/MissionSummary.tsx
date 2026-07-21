import { useState } from "react";
import type { MissionSummaryData } from "../lib/summarizeFinding";
import { getHardeningReport } from "../api/client";

type Props = {
  summary: MissionSummaryData;
  proxyLabel?: string | null;
  progress: number;
  hardening?: Array<{ title?: string; detail?: string; severity?: string }>;
  posture?: string | null;
  jobId?: string | null;
};

export function MissionSummary({
  summary,
  proxyLabel,
  progress,
  hardening,
  posture,
  jobId,
}: Props) {
  const [exportMsg, setExportMsg] = useState<string | null>(null);

  async function exportHardening() {
    if (!jobId) return;
    setExportMsg(null);
    try {
      const data = await getHardeningReport(jobId);
      const md =
        data.markdown ||
        (data.recommendations || [])
          .map(
            (r) =>
              `### ${r.title ?? "item"}${r.severity ? ` (${r.severity})` : ""}\n\n${r.detail ?? ""}\n`,
          )
          .join("\n");
      const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `hardening-${jobId}.md`;
      a.click();
      URL.revokeObjectURL(url);
      setExportMsg("Downloaded");
    } catch (err: unknown) {
      setExportMsg(err instanceof Error ? err.message : String(err));
    }
  }

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
        {posture && <span className="badge badge--ok">{posture}</span>}
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

      {hardening && hardening.length > 0 && (
        <div className="mission-summary__harden" aria-label="Hardening">
          <div className="section-label">
            Defense recommendations
            {jobId && (
              <>
                {" · "}
                <button
                  type="button"
                  className="btn"
                  style={{ fontSize: "0.75rem", padding: "0.1rem 0.4rem" }}
                  onClick={() => void exportHardening()}
                >
                  Export markdown
                </button>
                {exportMsg && <span className="arsenal__note"> · {exportMsg}</span>}
              </>
            )}
          </div>
          <ul className="plan-list">
            {hardening.slice(0, 8).map((row) => (
              <li key={row.title}>
                <strong>{row.title}</strong>
                {row.severity ? ` [${row.severity}]` : ""} — {row.detail}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="progress">
        <div className="progress__bar" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}
