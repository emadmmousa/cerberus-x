import { describe, expect, it } from "vitest";
import { mergeOsintSeeds, normalizeOsintSeed, validateOsintSeed } from "../lib/osintTargets";

describe("osintTargets", () => {
  it("normalizes username and email seeds", () => {
    expect(normalizeOsintSeed("username", "@alice")).toEqual({
      kind: "username",
      value: "alice",
      display: "@alice",
    });
    expect(normalizeOsintSeed("email", "Person@Corp.com").value).toBe("person@corp.com");
  });

  it("validates required values", () => {
    expect(validateOsintSeed("email", "bad")).toMatch(/valid email/i);
    expect(validateOsintSeed("domain", "corp.com")).toBeNull();
  });

  it("merges without duplicates", () => {
    const first = normalizeOsintSeed("email", "a@b.com");
    const merged = mergeOsintSeeds([first], normalizeOsintSeed("email", "a@b.com"));
    expect(merged).toHaveLength(1);
  });
});
