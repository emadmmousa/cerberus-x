import { describe, expect, it } from "vitest";
import {
  AI_LAB_SECTIONS,
  aiLabPageTitle,
  aiLabSectionsByGroup,
  isAiLabSectionId,
} from "../lib/aiLabSections";

describe("aiLabSections", () => {
  it("lists all AI Lab areas", () => {
    expect(AI_LAB_SECTIONS.length).toBe(4);
    expect(isAiLabSectionId("marketplace")).toBe(true);
    expect(isAiLabSectionId("invalid")).toBe(false);
  });

  it("groups sections for navigation", () => {
    const groups = aiLabSectionsByGroup();
    expect(groups).toHaveLength(3);
    expect(groups.flatMap((g) => g.sections)).toHaveLength(4);
  });

  it("maps routes to page titles", () => {
    expect(aiLabPageTitle()).toBe("AI Lab");
    expect(aiLabPageTitle("scaffolds")).toBe("Model Router");
    expect(aiLabPageTitle("marketplace")).toBe("Specialist Exchange");
    expect(aiLabPageTitle("hosting")).toBe("Cloud Control Plane");
    expect(aiLabPageTitle("dataset")).toBe("Training Corpus");
  });
});
