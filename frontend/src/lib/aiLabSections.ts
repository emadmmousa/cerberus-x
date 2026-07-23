export type AiLabSectionId = "scaffolds" | "marketplace" | "hosting" | "dataset";

export type AiLabSectionGroup = "Models & routing" | "Platform" | "Training data";

export type AiLabSection = {
  id: AiLabSectionId;
  path: `/ai-lab/${AiLabSectionId}`;
  label: string;
  icon: string;
  group: AiLabSectionGroup;
  description: string;
};

export const AI_LAB_SECTIONS: AiLabSection[] = [
  {
    id: "scaffolds",
    path: "/ai-lab/scaffolds",
    label: "Model Router",
    icon: "⇄",
    group: "Models & routing",
    description: "Inference routes, latency scores, and live platform capabilities.",
  },
  {
    id: "marketplace",
    path: "/ai-lab/marketplace",
    label: "Specialist Exchange",
    icon: "🛒",
    group: "Models & routing",
    description: "Browse cyber specialist recipes and deploy Pro inference routes.",
  },
  {
    id: "hosting",
    path: "/ai-lab/hosting",
    label: "Cloud Control Plane",
    icon: "☁",
    group: "Platform",
    description: "Managed hosting hooks, agent pulse telemetry, and Pro readiness.",
  },
  {
    id: "dataset",
    path: "/ai-lab/dataset",
    label: "Training Corpus",
    icon: "📚",
    group: "Training data",
    description: "Seed library and operator contributions for Model Forge fine-tuning.",
  },
];

const SECTION_IDS = new Set(AI_LAB_SECTIONS.map((s) => s.id));

export function isAiLabSectionId(value: string | undefined): value is AiLabSectionId {
  return Boolean(value && SECTION_IDS.has(value as AiLabSectionId));
}

export function aiLabSectionById(id: AiLabSectionId): AiLabSection {
  return AI_LAB_SECTIONS.find((s) => s.id === id)!;
}

export function aiLabSectionsByGroup(): Array<{ group: AiLabSectionGroup; sections: AiLabSection[] }> {
  const groups: AiLabSectionGroup[] = ["Models & routing", "Platform", "Training data"];
  return groups.map((group) => ({
    group,
    sections: AI_LAB_SECTIONS.filter((s) => s.group === group),
  }));
}

export function aiLabPageTitle(section?: string): string {
  if (isAiLabSectionId(section)) {
    return aiLabSectionById(section).label;
  }
  return "AI Lab";
}
