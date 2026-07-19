import { useState } from "react";
import { ProxyToggle } from "../components/ProxyToggle";
import { StatusPulse } from "../components/StatusPulse";
import { useMission } from "../hooks/useMission";

type Props = {
  target: string;
  onTargetChange: (target: string) => void;
};

export function MissionLaunch({ target, onTargetChange }: Props) {
  const [useProxy, setUseProxy] = useState(false);
  const [protocol, setProtocol] = useState<"http" | "https" | "socks5h">("http");
  const { taskId, status, error, launchFlash, launch, isActive } = useMission();

  async function handleRun() {
    if (!target.trim()) return;
    await launch({
      target: target.trim(),
      use_proxy: useProxy,
      proxy_protocol: protocol,
    });
  }

  return (
    <div className={launchFlash ? "launch-confirm" : undefined}>
      <h1 className="hero-title">CERBERUS-X</h1>
      <p className="hero-sub">Operator Console — Mission Launch</p>

      <div className="panel">
        <div className="field">
          <label htmlFor="target">Target</label>
          <input
            id="target"
            type="text"
            placeholder="example.com"
            value={target}
            onChange={(e) => onTargetChange(e.target.value)}
            disabled={isActive}
          />
        </div>

        <ProxyToggle
          enabled={useProxy}
          onChange={setUseProxy}
          protocol={protocol}
          onProtocolChange={setProtocol}
          disabled={isActive}
        />

        <div className="row" style={{ marginTop: "1rem" }}>
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => void handleRun()}
            disabled={!target.trim() || isActive}
          >
            Run Playbook
          </button>
        </div>

        {error && <p className="error-text">{error}</p>}
      </div>

      {(taskId || status) && (
        <div className="panel">
          <div className="panel__title">Mission Status</div>
          {taskId && (
            <p>
              <span className="result-card__meta">Task ID: </span>
              {taskId}
            </p>
          )}
          {status && (
            <>
              <div className="row">
                <StatusPulse state={status.state} />
                {status.use_proxy && (
                  <span className="badge badge--ok">
                    Proxy {status.proxy_protocol ?? protocol}
                  </span>
                )}
              </div>
              {status.error && <p className="error-text">{status.error}</p>}
              {status.phases && status.phases.length > 0 && (
                <div className="scroll-box" style={{ marginTop: "0.75rem" }}>
                  {status.phases.map((phase) => (
                    <div key={phase.phase} className="log-entry">
                      {phase.phase}
                      {phase.task_id ? ` — ${phase.task_id}` : ""}
                      {phase.error ? ` — ${phase.error}` : ""}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
