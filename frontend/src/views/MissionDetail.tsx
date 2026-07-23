import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { cancelMission, retryMission } from "../api/client";
import { BlackboardPanel } from "../components/BlackboardPanel";
import { MissionActivityPanel } from "../components/MissionActivityPanel";
import { MissionFindingsPanel } from "../components/MissionFindingsPanel";
import { MissionPhaseNav } from "../components/MissionPhaseNav";
import { MissionSummary } from "../components/MissionSummary";
import { PageHero } from "../components/PageHero";
import { PhaseCard } from "../components/PhaseCard";
import { useEventLog } from "../hooks/useEventLog";
import { collapseAiSteps, useMission } from "../hooks/useMission";
import {
  formatTimelineProgress,
  missionStateLabel,
  shortTaskId,
} from "../lib/missionSummary";
import { summarizeMission } from "../lib/summarizeFinding";

function statusTone(state?: string): "running" | "success" | "failure" | "pending" {
  const s = (state ?? "").toUpperCase();
  if (s === "SUCCESS") return "success";
  if (s === "FAILURE") return "failure";
  if (["PENDING", "STARTED", "RUNNING", "PROGRESS", "RETRY"].includes(s)) return "running";
  return "pending";
}

export function MissionDetail() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const {
    status,
    error,
    attachMission,
    isActive,
    phases,
    results,
    activeTarget,
    completedPhases,
    timelineLength,
    progressPercent,
  } = useMission();
  const {
    entries,
    levelFilter,
    setLevelFilter,
    textFilter,
    setTextFilter,
  } = useEventLog();

  useEffect(() => {
    setLifecycleState(null);
    setLifecycleNotice(null);
    if (id) void attachMission(id);
  }, [id, attachMission]);

  const missionSummary = useMemo(() => {
    if (!activeTarget && !status) return null;
    return summarizeMission(results, status?.state, activeTarget ?? status?.target ?? id);
  }, [activeTarget, status, results, id]);

  const aiSteps = useMemo(
    () => collapseAiSteps(status?.ai?.steps ?? []),
    [status?.ai?.steps],
  );

  const runningIndex = useMemo(
    () => phases.findIndex((p) => p.state === "running"),
    [phases],
  );
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [planOpen, setPlanOpen] = useState(true);
  const [copyMsg, setCopyMsg] = useState<string | null>(null);
  const [lifecycleNotice, setLifecycleNotice] = useState<string | null>(null);
  const [lifecycleState, setLifecycleState] = useState<string | null>(null);
  const [lifecycleBusy, setLifecycleBusy] = useState(false);
  const phaseRefs = useRef<Array<HTMLDivElement | null>>([]);

  useEffect(() => {
    if (runningIndex >= 0) {
      setExpandedIndex(runningIndex);
    }
  }, [runningIndex]);

  const focusPhase = (index: number) => {
    setExpandedIndex(index);
    requestAnimationFrame(() => {
      phaseRefs.current[index]?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    });
  };

  const taskId = status?.task_id ?? id;
  const target = status?.target || activeTarget || id;
  const displayedState = lifecycleState ?? status?.state;
  const tone = statusTone(displayedState);
  const stateLabel =
    displayedState?.toUpperCase() === "CANCEL_REQUESTED"
      ? "Cancel requested"
      : missionStateLabel(displayedState);
  const canCancel = ["PENDING", "STARTED"].includes((displayedState ?? "").toUpperCase());
  const canRetry = (displayedState ?? "").toUpperCase() === "FAILURE";

  async function copyTaskId() {
    try {
      await navigator.clipboard.writeText(taskId);
      setCopyMsg("Copied");
      window.setTimeout(() => setCopyMsg(null), 1800);
    } catch {
      setCopyMsg("Copy failed");
    }
  }

  async function requestCancellation() {
    setLifecycleBusy(true);
    setLifecycleNotice(null);
    try {
      const result = await cancelMission(taskId);
      setLifecycleState(result.state);
      setLifecycleNotice(
        "Cancel requested. Any current phase is allowed to finish collection; no running command was terminated.",
      );
    } catch (err) {
      setLifecycleNotice(
        `Could not request cancellation: ${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      setLifecycleBusy(false);
    }
  }

  async function retryFailedMission() {
    setLifecycleBusy(true);
    setLifecycleNotice(null);
    try {
      const result = await retryMission(taskId);
      await attachMission(result.task_id);
      navigate(`/missions/${encodeURIComponent(result.task_id)}`);
    } catch (err) {
      setLifecycleNotice(
        `Could not retry mission: ${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      setLifecycleBusy(false);
    }
  }

  return (
    <div className="mission-workspace">
      <PageHero
        crumbs={[
          { label: "Operations", to: "/missions" },
          { label: "Mission" },
        ]}
        title={target}
        status={{
          label: stateLabel,
          tone,
          pulse: isActive && tone === "running",
        }}
        badges={
          <>
            {status?.ai_mode && <span className="badge badge--ok">AI plan</span>}
            {status?.use_proxy && (
              <span className="badge badge--ok">Proxy {status.proxy_protocol ?? "on"}</span>
            )}
            {status?.ai?.posture && <span className="badge">{status.ai.posture}</span>}
          </>
        }
        meta={
          <>
            <button type="button" className="page-hero__id" onClick={() => void copyTaskId()}>
              {shortTaskId(taskId)}
              <span className="page-hero__id-action">Copy ID</span>
            </button>
            {copyMsg && <span className="page-hero__copied">{copyMsg}</span>}
            {timelineLength > 0 && (
              <span>{formatTimelineProgress(completedPhases, timelineLength)}</span>
            )}
          </>
        }
        progress={timelineLength > 0 ? progressPercent : null}
        progressAriaLabel={`Mission timeline ${progressPercent} percent complete`}
        actions={
          <>
            {canCancel && (
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => void requestCancellation()}
                disabled={lifecycleBusy}
              >
                Cancel mission
              </button>
            )}
            {canRetry && (
              <button
                type="button"
                className="btn btn--primary btn--sm"
                onClick={() => void retryFailedMission()}
                disabled={lifecycleBusy}
              >
                Retry mission
              </button>
            )}
            <Link to="/missions" className="btn btn--ghost btn--sm">
              All missions
            </Link>
          </>
        }
        error={error || status?.error || null}
      />

      {lifecycleNotice && (
        <p className="mission-workspace__notice" role="status">
          {lifecycleNotice}
        </p>
      )}

      {missionSummary && (
        <section className="mission-workspace__summary" aria-label="Status">
          <MissionSummary
            summary={missionSummary}
            proxyLabel={status?.use_proxy ? status.proxy_protocol ?? null : null}
            progress={progressPercent}
            hardening={status?.ai?.hardening}
            posture={status?.ai?.posture}
            jobId={status?.task_id}
          />
          <MissionFindingsPanel jobId={taskId} target={target} />
          <BlackboardPanel missionId={status?.task_id} />
        </section>
      )}

      {aiSteps.length > 0 && (
        <section className="panel mission-plan" aria-label="Plan">
          <button
            type="button"
            className="mission-plan__toggle"
            aria-expanded={planOpen}
            onClick={() => setPlanOpen((v) => !v)}
          >
            <span className="section-label">AI plan</span>
            <span className="mission-plan__count">{aiSteps.length} steps</span>
            <span className="mission-plan__chevron">{planOpen ? "−" : "+"}</span>
          </button>
          {planOpen && (
            <ul className="plan-list mission-plan__list">
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
          )}
        </section>
      )}

      <MissionPhaseNav
        phases={phases}
        runningIndex={runningIndex}
        selectedIndex={expandedIndex}
        onSelect={focusPhase}
      />

      <div className="mission-workspace__grid">
        <section className="mission-steps panel" aria-label="Steps">
          <div className="mission-steps__head">
            <div>
              <div className="section-label">Execution timeline</div>
              <p className="mission-steps__hint">
                Expand a step for tool output. The live step opens automatically.
              </p>
            </div>
            {phases.length > 0 && (
              <span className="mission-steps__count">{phases.length} phases</span>
            )}
          </div>

          <div className="phase-timeline phase-timeline--enhanced">
            {phases.length === 0 && (
              <p className="result-card__meta">Preparing steps…</p>
            )}
            {phases.map((phase, i) => (
              <PhaseCard
                key={`${phase.name}-${i}`}
                ref={(el) => {
                  phaseRefs.current[i] = el;
                }}
                phase={phase}
                index={i}
                isCurrent={i === runningIndex}
                isSelected={expandedIndex === i}
                open={expandedIndex === i}
                onToggle={() =>
                  setExpandedIndex((prev) => (prev === i ? null : i))
                }
                onNodeClick={() => focusPhase(i)}
              />
            ))}
          </div>
        </section>

        <MissionActivityPanel
          entries={entries}
          levelFilter={levelFilter}
          setLevelFilter={setLevelFilter}
          textFilter={textFilter}
          setTextFilter={setTextFilter}
          followLive={isActive}
        />
      </div>
    </div>
  );
}
