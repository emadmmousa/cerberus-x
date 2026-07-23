import { describe, expect, it } from "vitest";
import { ACCESS_GUARD_PRODUCT } from "../lib/accessGuard";
import {
  agentPulseSummary,
  cloudLinkStatusLabel,
  corpusPostureLabel,
  editionDisplayName,
  hostingSetupSteps,
  marketplaceEditionBadge,
  platformCapabilities,
  routingModeLabel,
  scaffoldDisplayName,
  taskCapabilityLabel,
} from "../lib/aiLabBranding";

describe("aiLabBranding", () => {
  it("maps platform waves to commercial capability names", () => {
    const caps = platformCapabilities({
      w4_rbac: true,
      w1_blackboard: true,
      w0_license: false,
    });
    expect(caps.map((cap) => cap.label)).toEqual([ACCESS_GUARD_PRODUCT, "Mission Brain"]);
  });

  it("uses commercial route and edition labels", () => {
    expect(scaffoldDisplayName("ollama-primary")).toBe("Primary Route");
    expect(routingModeLabel(true)).toBe("Consensus Routing");
    expect(editionDisplayName("community")).toBe("Community Edition");
    expect(marketplaceEditionBadge(false)).toBe("Community Edition");
    expect(taskCapabilityLabel("plan")).toBe("Mission Planning");
    expect(corpusPostureLabel("aggressive")).toBe("Offensive Lens");
    expect(corpusPostureLabel("defensive")).toBe("Defensive Lens");
    expect(corpusPostureLabel("")).toBe("All Lenses");
    expect(cloudLinkStatusLabel(false)).toBe("Standby");
    expect(
      hostingSetupSteps("community", { enabled: false }).filter((s) => s.required && !s.satisfied)
        .length,
    ).toBeGreaterThan(0);
    expect(agentPulseSummary({ ok: true, status: 200 })).toContain("200");
  });
});
