import { useMemo, useState } from "react";
import { AiModeToggle } from "../components/AiModeToggle";
import { MissionSummary } from "../components/MissionSummary";
import { PhaseCard } from "../components/PhaseCard";
import { ProxyToggle } from "../components/ProxyToggle";
import { useEventLog } from "../hooks/useEventLog";
import { useMission } from "../hooks/useMission";
import { summarizeMission } from "../lib/summarizeFinding";

type Props = {
  target: string;
  onTargetChange: (target: string) => void;
};

type StealthUi = "off" | "low" | "high";

function stealthToEvasion(level: StealthUi): "off" | "low" | "aggressive" {
  if (level === "off") return "off";
  if (level === "low") return "low";
  return "aggressive";
}

function formatTime(ts?: number): string {
  if (!ts) return new Date().toLocaleTimeString();
  return new Date(ts * 1000).toLocaleTimeString();
}

export function MissionControl({ target, onTargetChange }: Props) {
  const [useProxy, setUseProxy] = useState(false);
  const [protocol, setProtocol] = useState<"http" | "https" | "socks5h">("http");
  const [stealth, setStealth] = useState<StealthUi>("high");
  const [aiMode, setAiMode] = useState(false);
  const [nlGoal, setNlGoal] = useState("");
  const [confirmHighRisk, setConfirmHighRisk] = useState(true);
  const [optionsOpen, setOptionsOpen] = useState(false);
  const {
    status,
    error,
    launchFlash,
    launch,
    isActive,
    phases,
    results,
    activeTarget,
    completedPhases,
    pipelineLength,
  } = useMission();
  const { entries } = useEventLog();

  async function handleLaunch() {
    if (!target.trim() || isActive) return;
    await launch({
      target: target.trim(),
      use_proxy: useProxy,
      proxy_protocol: protocol,
      evasion: stealthToEvasion(stealth),
      ai_mode: aiMode,
      nl_goal: nlGoal.trim() || undefined,
      confirm_high_risk: confirmHighRisk,
    });
  }

  const progress =
    pipelineLength > 0 ? Math.round((completedPhases / pipelineLength) * 100) : 0;

  const missionSummary = useMemo(() => {
    if (!activeTarget && !status) return null;
    return summarizeMission(
      results,
      status?.state,
      activeTarget ?? target.trim(),
    );
  }, [activeTarget, status, results, target]);

  const aiSteps = status?.ai?.steps ?? [];
  const showRun = Boolean(missionSummary || phases.length > 0 || entries.length > 0);

  return (
    <div className={launchFlash ? "mission launch-confirm" : "mission"}>
      <section className="panel launch" aria-label="Start scan">
        <div className="launch__row">
          <div className="field launch__field">
            <label htmlFor="target">Website or host</label>
            <input
              id="target"
              type="text"
              placeholder="example.com"
              value={target}
              onChange={(e) => onTargetChange(e.target.value)}
              disabled={isActive}
              autoComplete="off"
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleLaunch();
              }}
            />
          </div>
          <button
            type="button"
            className="btn btn--primary launch__start"
            onClick={() => void handleLaunch()}
            disabled={!target.trim() || isActive}
          >
            {isActive ? "Running…" : "Start"}
          </button>
        </div>

        <div className="launch__meta">
          <button
            type="button"
            className="link-btn"
            aria-expanded={optionsOpen}
            onClick={() => setOptionsOpen((v) => !v)}
          >
            {optionsOpen ? "Hide options" : "Options"}
          </button>
          {(useProxy || aiMode || stealth !== "high") && !optionsOpen && (
            <span className="launch__chips">
              {stealth !== "high" && (
                <span className="chip">Stealth {stealth}</span>
              )}
              {useProxy && <span className="chip">Proxy</span>}
              {aiMode && <span className="chip">Smart plan</span>}
            </span>
          )}
        </div>

        {optionsOpen && (
          <div className="options" id="mission-options">
            <div className="field options__stealth">
              <label htmlFor="stealth">Stealth</label>
              <select
                id="stealth"
                value={stealth}
                onChange={(e) => setStealth(e.target.value as StealthUi)}
                disabled={isActive}
              >
                <option value="off">Off</option>
                <option value="low">Low</option>
                <option value="high">High</option>
              </select>
            </div>

            <ProxyToggle
              enabled={useProxy}
              onChange={setUseProxy}
              protocol={protocol}
              onProtocolChange={setProtocol}
              disabled={isActive}
            />

            <AiModeToggle
              enabled={aiMode}
              onChange={setAiMode}
              nlGoal={nlGoal}
              onNlGoalChange={setNlGoal}
              confirmHighRisk={confirmHighRisk}
              onConfirmHighRiskChange={setConfirmHighRisk}
              disabled={isActive}
            />
          </div>
        )}

        {error && <p className="error-text">{error}</p>}
        {status?.error && <p className="error-text">{status.error}</p>}
      </section>

      {showRun && (
        <>
          {missionSummary && (
            <section aria-label="Status">
              <div className="section-label">Status</div>
              <MissionSummary
                summary={missionSummary}
                proxyLabel={
                  status?.use_proxy ? (status.proxy_protocol ?? protocol) : null
                }
                progress={progress}
              />
            </section>
          )}

          {aiSteps.length > 0 && (
            <section className="panel" aria-label="Plan">
              <div className="section-label">Plan</div>
              <ul className="plan-list">
                {aiSteps.map((step, idx) => (
                  <li key={`${step.phase_name ?? "step"}-${idx}`}>
                    <span className="plan-list__name">
                      {step.phase_name ?? `Step ${idx + 1}`}
                    </span>
                    <span className="plan-list__reason">
                      {step.reason ?? "—"}
                    </span>
                  </li>
                ))}
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
                <PhaseCard key={phase.name} phase={phase} index={i} />
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
                    <span className="log-line__time">
                      {formatTime(entry.timestamp)}
                    </span>
                    <span
                      className={`log-line__lvl log-line__lvl--${entry.level}`}
                    >
                      {entry.level}
                    </span>
                    <span>{entry.message}</span>
                  </div>
                ))}
              </div>
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
