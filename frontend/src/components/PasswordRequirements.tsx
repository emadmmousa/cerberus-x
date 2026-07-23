import {
  passwordRequirements,
  type PasswordRequirement,
} from "../lib/passwordValidation";

type Props = {
  password: string;
  confirm?: string;
  title?: string;
  id?: string;
};

export function PasswordRequirements({
  password,
  confirm = "",
  title,
  id = "profile-password-requirements",
}: Props) {
  const rules = passwordRequirements(password, confirm);
  const active = password.length > 0 || confirm.length > 0;

  return (
    <div
      id={id}
      className={`password-requirements${active ? " password-requirements--active" : ""}`}
      aria-live="polite"
    >
      <p className="password-requirements__title">{title ?? "Password requirements"}</p>
      <ul className="password-requirements__list">
        {rules.map((rule) => (
          <RequirementRow key={rule.id} rule={rule} pending={!active} />
        ))}
      </ul>
    </div>
  );
}

function RequirementRow({
  rule,
  pending,
}: {
  rule: PasswordRequirement;
  pending: boolean;
}) {
  const state = pending ? "pending" : rule.met ? "met" : "unmet";

  return (
    <li className={`password-requirements__item password-requirements__item--${state}`}>
      <span className="password-requirements__mark" aria-hidden="true">
        {pending ? "○" : rule.met ? "✓" : "×"}
      </span>
      <span>{rule.label}</span>
    </li>
  );
}
