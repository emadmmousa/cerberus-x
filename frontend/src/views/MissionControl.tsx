import { useMemo, useState } from "react";
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
            {isActive ? "Operation Running\u2026" : "Launch Full Spectrum"}
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
          <div className="scroll-box scroll-box--tall">
            {entries.length === 0 && (
              <p className="result-card__meta">Awaiting telemetry…</p>
            )}
            {entries.map((entry) => (
              <div
                key={entry.id}
                className={`log-entry log-entry--${entry.level ?? "INFO"}`}
              >
                [{formatTime(entry.timestamp)}] {entry.level}: {entry.message}
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
