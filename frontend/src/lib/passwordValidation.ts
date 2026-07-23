export const PASSWORD_MIN_LENGTH = 8;

export type PasswordRequirement = {
  id: string;
  label: string;
  met: boolean;
};

export function passwordRequirements(
  password: string,
  confirm = "",
): PasswordRequirement[] {
  const rules: PasswordRequirement[] = [
    {
      id: "length",
      label: `At least ${PASSWORD_MIN_LENGTH} characters`,
      met: password.length >= PASSWORD_MIN_LENGTH,
    },
  ];

  if (confirm.length > 0 || password.length > 0) {
    rules.push({
      id: "match",
      label: "Passwords match",
      met: password.length > 0 && password === confirm,
    });
  }

  return rules;
}

export function passwordMeetsRequirements(password: string, confirm = ""): boolean {
  return passwordRequirements(password, confirm).every((rule) => rule.met);
}
