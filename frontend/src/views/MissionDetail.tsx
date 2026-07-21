import { useEffect, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { BlackboardPanel } from "../components/BlackboardPanel";
import { MissionSummary } from "../components/MissionSummary";
import { PhaseCard } from "../components/PhaseCard";
import { useEventLog } from "../hooks/useEventLog";
import { collapseAiSteps, useMission } from "../hooks/useMission";
import { summarizeMission } from "../lib/summarizeFinding";

function formatTime(ts?: number): string {
  if (!ts) return new Date().toLocaleTimeString();
  return new Date(ts * 1000).toLocaleTimeString();
}

export function MissionDetail() {
  const { id = "" } = useParams();
  const {
    status,
    error,
    attachMission,
    isActive,
    phases,
    results,
    activeTarget,
    completedPhases,
    pipelineLength,
  } = useMission();
  const { entries } = useEventLog();

  useEffect(() => {
    if (id) void attachMission(id);
  }, [id, attachMission]);

  const progress =
    pipelineLength > 0 ? Math.round((completedPhases / pipelineLength) * 100) : 0;

  const missionSummary = useMemo(() => {
    if (!activeTarget && !status) return null;
    return summarizeMission(results, status?.state, activeTarget ?? status?.target ?? id);
  }, [activeTarget, status, results, id]);

  const aiSteps = useMemo(
    () => collapseAiSteps(status?.ai?.steps ?? []),
    [status?.ai?.steps],
  );

  return (
    <div className="mission">
      <section className="panel launch" aria-label="Mission header">
        <div className="launch__row" style={{ alignItems: "center" }}>
          <div>
            <div className="section-label">Mission</div>
            <p className="plan-list__name">{status?.target || id}</p>
            <p className="result-card__meta">
              {status?.state ?? (isActive ? "RUNNING" : "—")}
              {status?.ai_mode ? " · AI" : ""}
            </p>
          </div>
          <Link to="/missions" className="link-btn">
            All missions
          </Link>
        </div>
        {error && <p className="error-text">{error}</p>}
        {status?.error && <p className="error-text">{status.error}</p>}
      </section>

      {missionSummary && (
        <section aria-label="Status">
          <div className="section-label">Status</div>
          <MissionSummary
            summary={missionSummary}
            proxyLabel={status?.use_proxy ? status.proxy_protocol ?? null : null}
            progress={progress}
            hardening={status?.ai?.hardening}
            posture={status?.ai?.posture}
            jobId={status?.task_id}
          />
          <BlackboardPanel missionId={status?.task_id} />
        </section>
      )}

      {aiSteps.length > 0 && (
        <section className="panel" aria-label="Plan">
          <div className="section-label">Plan</div>
          <ul className="plan-list">
            {aiSteps.map((step, idx) => {
              const conf = step.consensus?.confidence;
              const mode = step.consensus?.mode;
              return (
                <li key={`${step.phase_name ?? "step"}-${idx}`}>
                  <span className="plan-list__name">
                    {step.phase_name ?? `Step ${idx + 1}`}
                    {step.source === "multi_scaffold" && typeof conf === "number" && (
                      <span
                        className={`badge ${conf >= 0.5 ? "badge--ok" : "badge--warn"}`}
                        style={{ marginLeft: "0.4rem" }}
                      >
                        {mode ? `${mode} · ` : ""}
                        consensus {Math.round(conf * 100)}%
                      </span>
                    )}
                  </span>
                  <span className="plan-list__reason">{step.reason ?? "—"}</span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <div className="grid-mission">
        <section className="phase-timeline" aria-label="Steps">
          <div className="section-label">Steps</div>
          {phases.length === 0 && (
            <p className="result-card__meta">Preparing steps…</p>
          )}
          {phases.map((phase, i) => (
            <PhaseCard key={`${phase.name}-${i}`} phase={phase} index={i} />
          ))}
        </section>

        <aside className="mission-log" aria-label="Activity">
          <div className="section-label">Activity</div>
          <div className="log-scroll">
            {entries.length === 0 && (
              <p className="result-card__meta">No activity yet</p>
            )}
            {entries.map((entry, i) => (
              <div key={`${entry.timestamp}-${i}`} className="log-line">
                <span className="log-line__time">{formatTime(entry.timestamp)}</span>
                <span className={`log-line__lvl log-line__lvl--${entry.level}`}>
                  {entry.level}
                </span>
                <span>{entry.message}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
