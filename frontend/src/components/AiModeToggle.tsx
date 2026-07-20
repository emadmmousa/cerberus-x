type Props = {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  nlGoal: string;
  onNlGoalChange: (goal: string) => void;
  confirmHighRisk: boolean;
  onConfirmHighRiskChange: (confirm: boolean) => void;
  disabled?: boolean;
};

export function AiModeToggle({
  enabled,
  onChange,
  nlGoal,
  onNlGoalChange,
  confirmHighRisk,
  onConfirmHighRiskChange,
  disabled,
}: Props) {
  return (
    <div className="proxy-toggle" style={{ marginTop: "0.75rem" }}>
      <label className="proxy-toggle__label">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
        />{" "}
        AI Mode (adaptive planner)
      </label>
      {enabled && (
        <div style={{ marginTop: "0.5rem", display: "grid", gap: "0.5rem" }}>
          <div className="field">
            <label htmlFor="nl-goal">Mission goal (optional)</label>
            <input
              id="nl-goal"
              type="text"
              placeholder="e.g. Recon and prefer SQL injection checks"
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
              disabled={disabled}
            />{" "}
            Allow high-risk tools (exploit / creds)
          </label>
        </div>
      )}
    </div>
  );
}
