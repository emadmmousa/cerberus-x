import { describe, expect, it } from "vitest";
import {
  breachProviderChipLabel,
  breachProviderDisplayName,
  BREACH_VAULT_PRODUCT,
  LEAK_RADAR_PRODUCT,
} from "../lib/breachIntelBranding";

describe("breachIntelBranding", () => {
  it("maps provider ids to commercial product names", () => {
    expect(breachProviderDisplayName("dehashed")).toBe(BREACH_VAULT_PRODUCT);
    expect(breachProviderDisplayName("leakcheck")).toBe(LEAK_RADAR_PRODUCT);
  });

  it("formats provider status chips", () => {
    expect(breachProviderChipLabel("dehashed", true)).toBe("Breach Vault Live");
    expect(breachProviderChipLabel("leakcheck", false)).toBe("Leak Radar Standby");
  });
});
