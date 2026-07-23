import { describe, expect, it } from "vitest";
import {
  PASSWORD_MIN_LENGTH,
  passwordMeetsRequirements,
  passwordRequirements,
} from "../lib/passwordValidation";

describe("passwordValidation", () => {
  it("requires minimum length and matching confirmation", () => {
    const rules = passwordRequirements("short", "short");
    expect(rules.find((r) => r.id === "length")?.met).toBe(false);
    expect(rules.find((r) => r.id === "match")?.met).toBe(true);

    const ok = passwordRequirements("correcthorse", "correcthorse");
    expect(ok.every((r) => r.met)).toBe(true);
    expect(passwordMeetsRequirements("correcthorse", "correcthorse")).toBe(true);
  });

  it("exposes backend-aligned minimum length", () => {
    expect(PASSWORD_MIN_LENGTH).toBe(8);
    expect(passwordMeetsRequirements("1234567", "1234567")).toBe(false);
    expect(passwordMeetsRequirements("12345678", "12345678")).toBe(true);
  });
});
