import { useEffect, useMemo, useState } from "react";
import {
  exportFindingsReport,
  listFindings,
  type NormalizedFinding,
} from "../api/client";

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"] as const;

type Props = {
  jobId: string;
  target?: string | null;
};

function severityBadgeClass(severity: string): string {
  const token = severity.toLowerCase();
  if (token === "critical" || token === "high") return "badge--err";
  if (token === "medium") return "badge--warn";
  return "badge";
}

export function MissionFindingsPanel({ jobId, target }: Props) {
  const [rows, setRows] = useState<NormalizedFinding[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [exportMsg, setExportMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void listFindings({
      jobId,
      target: target ?? undefined,
      severity: severityFilter === "all" ? undefined : severityFilter,
      limit: 100,
    })
      .then((payload) => {
        if (cancelled) return;
        setRows(payload.findings ?? []);
        setTotal(payload.total ?? payload.count ?? 0);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setRows([]);
        setTotal(0);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, target, severityFilter]);

  const sortedRows = useMemo(() => {
    return [...rows].sort((a, b) => {
      const ar = SEVERITY_ORDER.indexOf(
        (a.severity || "info").toLowerCase() as (typeof SEVERITY_ORDER)[number],
      );
      const br = SEVERITY_ORDER.indexOf(
        (b.severity || "info").toLowerCase() as (typeof SEVERITY_ORDER)[number],
      );
      const ai = ar >= 0 ? ar : SEVERITY_ORDER.length;
      const bi = br >= 0 ? br : SEVERITY_ORDER.length;
      if (ai !== bi) return ai - bi;
      return (b.last_seen || "").localeCompare(a.last_seen || "");
    });
  }, [rows]);

  async function downloadExport(format: "json" | "markdown") {
    setExportMsg(null);
    try {
      const data = await exportFindingsReport(jobId, format);
      const blob =
        format === "markdown"
          ? new Blob([String(data)], { type: "text/markdown;charset=utf-8" })
          : new Blob([JSON.stringify(data, null, 2)], {
              type: "application/json;charset=utf-8",
            });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `findings-${jobId}.${format === "markdown" ? "md" : "json"}`;
      anchor.click();
      URL.revokeObjectURL(url);
      setExportMsg(format === "markdown" ? "Markdown downloaded" : "JSON downloaded");
    } catch (err: unknown) {
      setExportMsg(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <section className="panel mission-findings" aria-label="Normalized findings">
      <div className="mission-findings__head">
        <div>
          <div className="section-label">Findings</div>
          <p className="mission-findings__hint">
            Deduplicated, evidence-backed observations from this mission.
          </p>
        </div>
        <div className="mission-findings__actions">
          <label className="mission-findings__filter">
            <span className="sr-only">Severity filter</span>
            <select
              value={severityFilter}
              onChange={(event) => setSeverityFilter(event.target.value)}
              aria-label="Filter by severity"
            >
              <option value="all">All severities</option>
              {SEVERITY_ORDER.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => void downloadExport("json")}
          >
            Export JSON
          </button>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => void downloadExport("markdown")}
          >
            Export Markdown
          </button>
        </div>
      </div>

      {exportMsg && (
        <p className="mission-findings__notice" role="status">
          {exportMsg}
        </p>
      )}

      {loading && <p className="result-card__meta">Loading findings…</p>}
      {error && <p className="mission-findings__error">{error}</p>}

      {!loading && !error && sortedRows.length === 0 && (
        <p className="result-card__meta">
          No normalized findings yet. Raw tool output remains in the execution timeline.
        </p>
      )}

      {!loading && !error && sortedRows.length > 0 && (
        <>
          <p className="mission-findings__count">
            Showing {sortedRows.length} of {total}
          </p>
          <ol className="mission-findings__list">
            {sortedRows.map((row) => (
              <li key={row.fingerprint || row.id} className="mission-findings__item">
                <div className="mission-findings__item-head">
                  <span className={`badge ${severityBadgeClass(row.severity)}`}>
                    {row.severity}
                  </span>
                  <strong>{row.title}</strong>
                </div>
                <div className="mission-findings__meta">
                  {row.tool && <span>Tool: {row.tool}</span>}
                  {row.endpoint && <span>Endpoint: {row.endpoint}</span>}
                  {row.observation_count != null && row.observation_count > 1 && (
                    <span>Seen {row.observation_count}×</span>
                  )}
                  {row.evidence?.length ? (
                    <span>
                      Evidence:{" "}
                      {row.evidence[row.evidence.length - 1]?.available
                        ? `phase ${row.evidence[row.evidence.length - 1]?.phase ?? "—"}`
                        : "unavailable"}
                    </span>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
