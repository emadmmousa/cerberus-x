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
    <div className="options-block">
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
          <span className="options-block__hint"> Adaptive steps</span>
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
              disabled={disabled}
            />{" "}
            Allow risky tools (on by default)
          </label>
        </div>
      )}
    </div>
  );
}
