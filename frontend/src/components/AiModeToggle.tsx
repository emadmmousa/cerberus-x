type PlaybookOption = {
  path: string;
  name: string;
  recommended_for?: string[];
};

type Props = {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  nlGoal: string;
  onNlGoalChange: (goal: string) => void;
  confirmHighRisk: boolean;
  onConfirmHighRiskChange: (confirm: boolean) => void;
  posture: "balanced" | "aggressive" | "defensive";
  onPostureChange: (posture: "balanced" | "aggressive" | "defensive") => void;
  playbook: string;
  onPlaybookChange: (path: string) => void;
  playbooks?: PlaybookOption[];
  disabled?: boolean;
};

export function AiModeToggle({
  enabled,
  onChange,
  nlGoal,
  onNlGoalChange,
  confirmHighRisk,
  onConfirmHighRiskChange,
  posture,
  onPostureChange,
  playbook,
  onPlaybookChange,
  playbooks = [],
  disabled,
}: Props) {
  return (
    <div className="options-block">
      <div className="field">
        <label htmlFor="posture">Posture</label>
        <select
          id="posture"
          value={posture}
          onChange={(e) =>
            onPostureChange(
              e.target.value as "balanced" | "aggressive" | "defensive",
            )
          }
          disabled={disabled}
        >
          <option value="balanced">Balanced (offense + defense)</option>
          <option value="aggressive">Aggressive (offense)</option>
          <option value="defensive">Defensive (hardening)</option>
        </select>
      </div>

      <div className="field">
        <label htmlFor="playbook">Playbook</label>
        <select
          id="playbook"
          value={playbook}
          onChange={(e) => onPlaybookChange(e.target.value)}
          disabled={disabled}
        >
          {playbooks.length === 0 && (
            <option value={playbook}>{playbook}</option>
          )}
          {playbooks.map((pb) => (
            <option key={pb.path} value={pb.path}>
              {pb.name}
              {pb.recommended_for?.includes(posture) ? " ★" : ""}
            </option>
          ))}
        </select>
        <p className="options-block__hint">{playbook}</p>
      </div>

      <label className="toggle-row options-block__toggle">
        <span className="toggle">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => onChange(e.target.checked)}
            disabled={disabled}
            aria-label="Smart plan"
          />
          <span className="toggle__track">
            <span className="toggle__thumb" />
          </span>
        </span>
        <span>
          <strong>Smart plan</strong>
          <span className="options-block__hint"> Adaptive AI steps</span>
        </span>
      </label>
      {enabled && (
        <div className="options-block__body">
          <div className="field">
            <label htmlFor="nl-goal">Goal (optional)</label>
            <input
              id="nl-goal"
              type="text"
              placeholder="e.g. Check for SQL injection"
              value={nlGoal}
              onChange={(e) => onNlGoalChange(e.target.value)}
              disabled={disabled}
            />
          </div>
          <label className="proxy-toggle__label">
            <input
              type="checkbox"
              checked={confirmHighRisk}
              onChange={(e) => onConfirmHighRiskChange(e.target.checked)}
              disabled={disabled || posture === "defensive"}
            />{" "}
            Allow risky tools
            {posture === "defensive" ? " (off in defensive)" : " (on by default)"}
          </label>
        </div>
      )}
    </div>
  );
}
