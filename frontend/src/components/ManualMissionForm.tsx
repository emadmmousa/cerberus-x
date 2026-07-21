import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listPlaybooks, type PlaybookCatalogEntry } from "../api/client";
import { AiModeToggle } from "./AiModeToggle";
import { ArsenalPanel } from "./ArsenalPanel";
import { ProxyToggle } from "./ProxyToggle";
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

export type ManualMissionPrefill = Partial<{
  target: string;
  posture: "balanced" | "aggressive" | "defensive";
  nl_goal: string;
  stealth: StealthUi;
  ai_mode: boolean;
}>;

type Props = {
  prefill?: ManualMissionPrefill | null;
  /** When false, call onLaunched instead of navigating away. Default true. */
  navigateOnLaunch?: boolean;
  onLaunched?: (taskId: string) => void;
};

export function ManualMissionForm({
  prefill,
  navigateOnLaunch = true,
  onLaunched,
}: Props) {
  const navigate = useNavigate();
  const [target, setTarget] = useState(prefill?.target ?? "");
  const [useProxy, setUseProxy] = useState(false);
  const [protocol, setProtocol] = useState<"http" | "https" | "socks5h">("http");
  const [stealth, setStealth] = useState<StealthUi>(prefill?.stealth ?? "high");
  const [aiMode, setAiMode] = useState(prefill?.ai_mode ?? false);
  const [nlGoal, setNlGoal] = useState(prefill?.nl_goal ?? "");
  const [confirmHighRisk, setConfirmHighRisk] = useState(true);
  const [posture, setPosture] = useState<"balanced" | "aggressive" | "defensive">(
    prefill?.posture ?? "balanced",
  );
  const [playbook, setPlaybook] = useState(
    POSTURE_PLAYBOOK[prefill?.posture ?? "balanced"],
  );
  const [playbooks, setPlaybooks] = useState<PlaybookCatalogEntry[]>([]);
  const [optionsOpen, setOptionsOpen] = useState(Boolean(prefill));
  const { launch, isActive, error, status } = useMission();

  useEffect(() => {
    if (!prefill) return;
    if (prefill.target != null) setTarget(prefill.target);
    if (prefill.posture) setPosture(prefill.posture);
    if (prefill.nl_goal != null) setNlGoal(prefill.nl_goal);
    if (prefill.stealth) setStealth(prefill.stealth);
    if (prefill.ai_mode != null) setAiMode(prefill.ai_mode);
    setOptionsOpen(true);
  }, [prefill]);

  useEffect(() => {
    listPlaybooks()
      .then((data) => setPlaybooks(data.playbooks ?? []))
      .catch(() => setPlaybooks([]));
  }, []);

  useEffect(() => {
    setPlaybook(POSTURE_PLAYBOOK[posture]);
  }, [posture]);

  useEffect(() => {
    if (!status?.task_id) return;
    if (navigateOnLaunch) {
      navigate(`/missions/${status.task_id}`, { replace: true });
      return;
    }
    onLaunched?.(status.task_id);
  }, [status?.task_id, navigateOnLaunch, onLaunched, navigate]);

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
    <section className="panel launch" aria-label="Manual mission">
      <div className="section-label">Manual mission</div>
      <p className="section-sub">
        Configure target and options, then start without the chat agent.
      </p>
      <div className="launch__row">
        <div className="field launch__field">
          <label htmlFor="manual-target">Website or host</label>
          <input
            id="manual-target"
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
            <label htmlFor="manual-stealth">Stealth</label>
            <select
              id="manual-stealth"
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
  );
}
