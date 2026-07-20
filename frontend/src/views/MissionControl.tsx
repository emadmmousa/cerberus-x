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

function formatTime(ts?: number): string {
  if (!ts) return new Date().toLocaleTimeString();
  return new Date(ts * 1000).toLocaleTimeString();
}

export function MissionControl({ target, onTargetChange }: Props) {
  const [useProxy, setUseProxy] = useState(false);
  const [protocol, setProtocol] = useState<"http" | "https" | "socks5h">("http");
  const [evasion, setEvasion] = useState<
    "low" | "medium" | "high" | "aggressive" | "off"
  >("aggressive");
  const [aiMode, setAiMode] = useState(false);
  const [nlGoal, setNlGoal] = useState("");
  const [confirmHighRisk, setConfirmHighRisk] = useState(false);
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
      evasion,
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

  return (
    <div className={launchFlash ? "launch-confirm" : undefined}>
      <h1 className="hero-title">CERBERUS-X</h1>
      <p className="hero-sub">Unified Operations Launcher</p>

      <div className="panel launcher">
        <div className="launcher__row">
          <div className="field">
            <label htmlFor="target">Target URL</label>
            <input
              id="target"
              type="text"
              placeholder="https://target.example.com"
              value={target}
              onChange={(e) => onTargetChange(e.target.value)}
              disabled={isActive}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleLaunch();
              }}
            />
          </div>
          <button
            type="button"
            className="btn btn--primary launcher__launch"
            onClick={() => void handleLaunch()}
            disabled={!target.trim() || isActive}
          >
            {isActive
              ? "Operation Running\u2026"
              : aiMode
                ? "Launch AI Mission"
                : "Launch Full Spectrum"}
          </button>
        </div>

        <div className="field" style={{ maxWidth: 220, marginBottom: "0.75rem" }}>
          <label htmlFor="evasion-level">WAF Evasion</label>
          <select
            id="evasion-level"
            value={evasion}
            onChange={(e) =>
              setEvasion(
                e.target.value as
                  | "low"
                  | "medium"
                  | "high"
                  | "aggressive"
                  | "off",
              )
            }
            disabled={isActive}
          >
            <option value="off">off</option>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
            <option value="aggressive">aggressive</option>
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

        {error && <p className="error-text">{error}</p>}
      </div>

      {missionSummary && (
        <MissionSummary
          summary={missionSummary}
          proxyLabel={
            status?.use_proxy ? (status.proxy_protocol ?? protocol) : null
          }
          progress={progress}
        />
      )}
      {status?.error && <p className="error-text">{status.error}</p>}

      {aiSteps.length > 0 && (
        <div className="panel" style={{ marginBottom: "1rem" }}>
          <div className="panel__title">AI decisions</div>
          <ul className="result-card__bullets">
            {aiSteps.map((step, idx) => (
              <li key={`${step.phase_name ?? "step"}-${idx}`}>
                <strong>{step.phase_name ?? `step ${idx + 1}`}</strong>
                {step.source ? ` [${step.source}]` : ""}: {step.reason ?? "—"}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid-mission">
        <section className="phase-timeline">
          <div className="panel__title">Attack Pipeline</div>
          {phases.length === 0 && (
            <p className="result-card__meta">Loading pipeline…</p>
          )}
          {phases.map((phase, i) => (
            <PhaseCard key={phase.name} phase={phase} index={i} />
          ))}
        </section>

        <aside className="mission-log">
          <div className="panel__title">Live Event Stream</div>
          <div className="log-scroll">
            {entries.length === 0 && (
              <p className="result-card__meta">Waiting for events…</p>
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
