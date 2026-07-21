import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listPlaybooks, type PlaybookCatalogEntry } from "../api/client";
import { AiModeToggle } from "../components/AiModeToggle";
import { ArsenalPanel } from "../components/ArsenalPanel";
import { ProxyToggle } from "../components/ProxyToggle";
import { useMission } from "../hooks/useMission";

type StealthUi = "off" | "low" | "high";

const POSTURE_PLAYBOOK: Record<
  "balanced" | "aggressive" | "defensive",
  string
> = {
  balanced: "playbooks/balanced_offense_defense.yaml",
  aggressive: "playbooks/complete_dark_arsenal.yaml",
  defensive: "playbooks/defensive_audit.yaml",
};

function stealthToEvasion(level: StealthUi): "off" | "low" | "aggressive" {
  if (level === "off") return "off";
  if (level === "low") return "low";
  return "aggressive";
}

export function NewMission() {
  const navigate = useNavigate();
  const [target, setTarget] = useState("");
  const [useProxy, setUseProxy] = useState(false);
  const [protocol, setProtocol] = useState<"http" | "https" | "socks5h">("http");
  const [stealth, setStealth] = useState<StealthUi>("high");
  const [aiMode, setAiMode] = useState(false);
  const [nlGoal, setNlGoal] = useState("");
  const [confirmHighRisk, setConfirmHighRisk] = useState(true);
  const [posture, setPosture] = useState<"balanced" | "aggressive" | "defensive">(
    "balanced",
  );
  const [playbook, setPlaybook] = useState(POSTURE_PLAYBOOK.balanced);
  const [playbooks, setPlaybooks] = useState<PlaybookCatalogEntry[]>([]);
  const [optionsOpen, setOptionsOpen] = useState(false);
  const { launch, isActive, error, status } = useMission();

  useEffect(() => {
    listPlaybooks()
      .then((data) => setPlaybooks(data.playbooks ?? []))
      .catch(() => setPlaybooks([]));
  }, []);

  useEffect(() => {
    setPlaybook(POSTURE_PLAYBOOK[posture]);
  }, [posture]);

  useEffect(() => {
    if (status?.task_id && status.state !== "PENDING") {
      navigate(`/missions/${status.task_id}`, { replace: true });
    } else if (status?.task_id) {
      navigate(`/missions/${status.task_id}`, { replace: true });
    }
  }, [status?.task_id, status?.state, navigate]);

  async function handleLaunch() {
    if (!target.trim() || isActive) return;
    await launch({
      target: target.trim(),
      use_proxy: useProxy,
      proxy_protocol: protocol,
      evasion: stealthToEvasion(stealth),
      ai_mode: aiMode,
      nl_goal: nlGoal.trim() || undefined,
      confirm_high_risk: posture === "defensive" ? false : confirmHighRisk,
      posture,
      playbook,
    });
  }

  return (
    <div className="mission">
      <section className="panel launch" aria-label="Start mission">
        <div className="section-label">New mission</div>
        <div className="launch__row">
          <div className="field launch__field">
            <label htmlFor="target">Website or host</label>
            <input
              id="target"
              type="text"
              placeholder="example.com"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
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
              posture={posture}
              onPostureChange={setPosture}
              playbook={playbook}
              onPlaybookChange={setPlaybook}
              playbooks={playbooks}
              disabled={isActive}
            />

            <ArsenalPanel disabled={isActive} />
          </div>
        )}

        {error && <p className="error-text">{error}</p>}
      </section>
    </div>
  );
}
