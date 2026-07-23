import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listPlaybooks, getProxyStatus, type PlaybookCatalogEntry } from "../api/client";
import { ArsenalPanel } from "./ArsenalPanel";
import { ProxyToggle } from "./ProxyToggle";
import { useMission } from "../hooks/useMission";

type StealthUi = "off" | "low" | "high";
type PostureUi = "balanced" | "aggressive" | "defensive";

const POSTURE_PLAYBOOK: Record<PostureUi, string> = {
  balanced: "playbooks/balanced_offense_defense.yaml",
  aggressive: "playbooks/complete_dark_arsenal.yaml",
  defensive: "playbooks/defensive_audit.yaml",
};

const POSTURE_OPTIONS: { id: PostureUi; label: string; hint: string }[] = [
  { id: "aggressive", label: "Aggressive", hint: "Full offense" },
  { id: "balanced", label: "Balanced", hint: "Offense + defense" },
  { id: "defensive", label: "Defensive", hint: "Exposure audit" },
];

function stealthToEvasion(level: StealthUi): "off" | "low" | "aggressive" {
  if (level === "off") return "off";
  if (level === "low") return "low";
  return "aggressive";
}

function playbookLabel(path: string, playbooks: PlaybookCatalogEntry[]): string {
  const hit = playbooks.find((row) => row.path === path);
  if (hit?.name) return hit.name;
  const tail = path.split("/").pop() ?? path;
  return tail.replace(/\.yaml$/, "").replace(/_/g, " ");
}

export type ManualMissionPrefill = Partial<{
  target: string;
  posture: PostureUi;
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
  const [useProxy, setUseProxy] = useState(true);
  const [protocol, setProtocol] = useState<"http" | "https" | "socks5h">("http");
  const [stealth, setStealth] = useState<StealthUi>(prefill?.stealth ?? "high");
  const [aiMode, setAiMode] = useState(prefill?.ai_mode ?? false);
  const [nlGoal, setNlGoal] = useState(prefill?.nl_goal ?? "");
  const [confirmHighRisk, setConfirmHighRisk] = useState(true);
  const [posture, setPosture] = useState<PostureUi>(prefill?.posture ?? "aggressive");
  const [playbook, setPlaybook] = useState(POSTURE_PLAYBOOK[prefill?.posture ?? "aggressive"]);
  const [playbooks, setPlaybooks] = useState<PlaybookCatalogEntry[]>([]);
  const [advancedOpen, setAdvancedOpen] = useState(Boolean(prefill));
  const { launch, isActive, error, status } = useMission();

  const playbookName = useMemo(
    () => playbookLabel(playbook, playbooks),
    [playbook, playbooks],
  );

  useEffect(() => {
    if (!prefill) return;
    if (prefill.target != null) setTarget(prefill.target);
    if (prefill.posture) setPosture(prefill.posture);
    if (prefill.nl_goal != null) setNlGoal(prefill.nl_goal);
    if (prefill.stealth) setStealth(prefill.stealth);
    if (prefill.ai_mode != null) setAiMode(prefill.ai_mode);
    setAdvancedOpen(true);
  }, [prefill]);

  useEffect(() => {
    listPlaybooks()
      .then((data) => setPlaybooks(data.playbooks ?? []))
      .catch(() => setPlaybooks([]));
    getProxyStatus()
      .then((data) => {
        if (data.configured) setUseProxy(true);
      })
      .catch(() => undefined);
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
    <section className="manual-mission" aria-label="Manual mission">
      <div className="manual-mission__scroll">
        <header className="manual-mission__header">
          <p className="manual-mission__eyebrow">Direct launch</p>
          <h2 className="manual-mission__title">Manual mission</h2>
          <p className="manual-mission__lead">
            Start a playbook run against an authorized target — no chat agent required.
          </p>
        </header>

        <div className="manual-mission__card">
          <div className="field manual-mission__target">
            <label htmlFor="manual-target">Target</label>
            <input
              id="manual-target"
              className="manual-mission__target-input"
              type="text"
              placeholder="example.com or https://app.example.com"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              disabled={isActive}
              autoComplete="off"
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleLaunch();
              }}
            />
            <p className="manual-mission__hint">
              Hostname, URL, or IP must be on your authorized target list.
            </p>
          </div>

          <fieldset className="manual-mission__posture">
            <legend className="manual-mission__legend">Posture</legend>
            <div className="manual-mission__chips" role="radiogroup" aria-label="Mission posture">
              {POSTURE_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  role="radio"
                  aria-checked={posture === option.id}
                  className={`manual-mission__chip${posture === option.id ? " manual-mission__chip--active" : ""}`}
                  disabled={isActive}
                  onClick={() => setPosture(option.id)}
                >
                  <span className="manual-mission__chip-label">{option.label}</span>
                  <span className="manual-mission__chip-hint">{option.hint}</span>
                </button>
              ))}
            </div>
            <p className="manual-mission__playbook-hint">
              Playbook: <span>{playbookName}</span>
            </p>
          </fieldset>

          <div className="manual-mission__quick">
            <div className="field manual-mission__quick-field">
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

            <label className="manual-mission__toggle">
              <input
                type="checkbox"
                checked={useProxy}
                onChange={(e) => setUseProxy(e.target.checked)}
                disabled={isActive}
              />
              <span>
                <strong>Proxy</strong>
                <span className="manual-mission__toggle-hint">Route via worker</span>
              </span>
            </label>

            <label className="manual-mission__toggle">
              <input
                type="checkbox"
                checked={aiMode}
                onChange={(e) => setAiMode(e.target.checked)}
                disabled={isActive}
              />
              <span>
                <strong>Smart plan</strong>
                <span className="manual-mission__toggle-hint">Adaptive AI steps</span>
              </span>
            </label>
          </div>

          {aiMode && (
            <div className="field manual-mission__goal">
              <label htmlFor="manual-nl-goal">Goal (optional)</label>
              <input
                id="manual-nl-goal"
                type="text"
                placeholder="e.g. Hunt SQLi on login forms"
                value={nlGoal}
                onChange={(e) => setNlGoal(e.target.value)}
                disabled={isActive}
              />
            </div>
          )}

          <button
            type="button"
            className="btn btn--primary manual-mission__start"
            onClick={() => void handleLaunch()}
            disabled={!target.trim() || isActive}
          >
            {isActive ? "Launching…" : "Start mission"}
          </button>

          {error && <p className="error-text manual-mission__error">{error}</p>}
        </div>

        <div className="manual-mission__advanced">
          <button
            type="button"
            className="manual-mission__advanced-toggle"
            aria-expanded={advancedOpen}
            onClick={() => setAdvancedOpen((open) => !open)}
          >
            <span>{advancedOpen ? "Hide advanced" : "Advanced options"}</span>
            <span className="manual-mission__advanced-chevron" aria-hidden>
              {advancedOpen ? "−" : "+"}
            </span>
          </button>

          {advancedOpen && (
            <div className="manual-mission__advanced-body">
              <div className="field">
                <label htmlFor="manual-playbook">Playbook override</label>
                <select
                  id="manual-playbook"
                  value={playbook}
                  onChange={(e) => setPlaybook(e.target.value)}
                  disabled={isActive}
                >
                  {playbooks.length === 0 && <option value={playbook}>{playbook}</option>}
                  {playbooks.map((pb) => (
                    <option key={pb.path} value={pb.path}>
                      {pb.name}
                      {pb.recommended_for?.includes(posture) ? " ★" : ""}
                    </option>
                  ))}
                </select>
                <p className="manual-mission__hint">{playbook}</p>
              </div>

              {posture !== "defensive" && (
                <label className="manual-mission__toggle manual-mission__toggle--block">
                  <input
                    type="checkbox"
                    checked={confirmHighRisk}
                    onChange={(e) => setConfirmHighRisk(e.target.checked)}
                    disabled={isActive}
                  />
                  <span>
                    <strong>Allow risky tools</strong>
                    <span className="manual-mission__toggle-hint">
                      sqlmap, metasploit, hydra, etc.
                    </span>
                  </span>
                </label>
              )}

              <ProxyToggle
                enabled={useProxy}
                onChange={setUseProxy}
                protocol={protocol}
                onProtocolChange={setProtocol}
                disabled={isActive}
              />

              <ArsenalPanel disabled={isActive} />
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
