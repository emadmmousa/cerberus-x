import { useState } from "react";
import { PhaseCard } from "../components/PhaseCard";
import { ProxyToggle } from "../components/ProxyToggle";
import { StatusPulse } from "../components/StatusPulse";
import { useEventLog } from "../hooks/useEventLog";
import { useMission } from "../hooks/useMission";

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
  const {
    status,
    error,
    launchFlash,
    launch,
    isActive,
    phases,
    activeTarget,
    totalFindings,
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
    });
  }

  const progress =
    pipelineLength > 0 ? Math.round((completedPhases / pipelineLength) * 100) : 0;

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

        <ProxyToggle
          enabled={useProxy}
          onChange={setUseProxy}
          protocol={protocol}
          onProtocolChange={setProtocol}
          disabled={isActive}
        />

        {error && <p className="error-text">{error}</p>}
      </div>

      {(status || activeTarget) && (
        <div className="panel mission-summary">
          <div className="mission-summary__head">
            <StatusPulse state={status?.state ?? "PENDING"} />
            {activeTarget && (
              <span className="mission-summary__target">{activeTarget}</span>
            )}
            {status?.use_proxy && (
              <span className="badge badge--ok">
                Proxy {status.proxy_protocol ?? protocol}
              </span>
            )}
            <span className="mission-summary__stat">
              {completedPhases}/{pipelineLength} phases
            </span>
            <span className="mission-summary__stat">{totalFindings} findings</span>
          </div>
          <div className="progress">
            <div className="progress__bar" style={{ width: `${progress}%` }} />
          </div>
          {status?.error && <p className="error-text">{status.error}</p>}
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
