import { ACCESS_GUARD_PRODUCT } from "./accessGuard";

export type PlatformCapability = {
  id: string;
  label: string;
  description: string;
  icon: string;
};

const WAVE_CAPABILITIES: Record<string, Omit<PlatformCapability, "id">> = {
  w0_license: {
    label: "License Pack",
    description: "Edition-aware packaging and feature gates.",
    icon: "📦",
  },
  w1_blackboard: {
    label: "Mission Brain",
    description: "Shared mission memory across every phase.",
    icon: "🧠",
  },
  w1_prompt_guard: {
    label: "Prompt Shield",
    description: "Blocks unsafe prompts and injection attempts.",
    icon: "🛡",
  },
  w2_training: {
    label: "Model Forge",
    description: "Harvest loops and automated retraining.",
    icon: "⚒",
  },
  w3_dataset: {
    label: "Training Corpus",
    description: "Operator-contributed fine-tuning examples.",
    icon: "📚",
  },
  w4_rbac: {
    label: ACCESS_GUARD_PRODUCT,
    description: "Role enforcement and authorized scope.",
    icon: "🔐",
  },
  w5_open_core: {
    label: "Open Core",
    description: "Community scaffold and tool baseline.",
    icon: "◈",
  },
};

const SCAFFOLD_NAMES: Record<string, string> = {
  "ollama-primary": "Primary Route",
  "ollama-fallback": "Failover Route",
};

export function platformCapabilities(
  waves?: Record<string, boolean>,
): PlatformCapability[] {
  if (!waves) return [];
  return Object.entries(waves)
    .filter(([, enabled]) => enabled)
    .map(([id]) => ({
      id,
      ...(WAVE_CAPABILITIES[id] ?? {
        label: humanizeToken(id),
        description: "Platform module",
        icon: "◈",
      }),
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

export function scaffoldDisplayName(id: string): string {
  return SCAFFOLD_NAMES[id] ?? humanizeToken(id);
}

export function scaffoldTechnicalLabel(id: string): string {
  return id;
}

export function modelDisplayName(model?: string | null): string {
  const value = (model ?? "").trim();
  if (!value) return "Firebreak Model";
  if (value.toLowerCase() === "firebreak") return "Firebreak Model";
  return value;
}

export function foundationModelLabel(baseModel?: string | null): string {
  return (baseModel ?? "").trim() || "Foundation model pending";
}

export function editionDisplayName(edition?: string): string {
  const value = (edition ?? "").trim().toLowerCase();
  if (value === "community") return "Community Edition";
  if (value === "pro") return "Pro Edition";
  if (!value) return "Standard Edition";
  return `${edition} Edition`;
}

export function routingModeLabel(multiScaffold?: boolean): string {
  return multiScaffold ? "Consensus Routing" : "Single Route";
}

export function costRoutingLabel(enabled?: boolean): string | null {
  if (!enabled) return null;
  return "Smart Cost Routing";
}

export function ssoDisplayLabel(ready?: boolean, preferred?: string | null): string {
  if (!ready) return "Local sign-in only";
  const provider = (preferred ?? "configured").replace(/^auth0$/i, "Auth0");
  return `Enterprise Sign-In · ${provider}`;
}

export function latencyLabel(ms?: number | null): string {
  if (ms == null || Number.isNaN(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function costPer1kLabel(value?: number | null): string {
  const n = Number(value ?? 0);
  return `$${n.toFixed(3)} / 1K tokens`;
}

export function healthStatusLabel(ok?: boolean): string {
  return ok ? "Online" : "Offline";
}

export type MarketplaceRecipe = {
  id: string;
  label?: string;
  category?: string;
  tasks?: string[];
  notes?: string;
  model?: string;
  base_url_hint?: string;
  license?: string;
  source?: string;
  kind?: string;
};

const TASK_LABELS: Record<string, string> = {
  plan: "Mission Planning",
  decide: "Tactical Decisions",
  harden: "Hardening Guidance",
  summarize: "Executive Summary",
  recon: "Reconnaissance",
};

const CATEGORY_ICONS: Record<string, string> = {
  "Core platform": "◈",
  "Reconnaissance & OSINT": "🔍",
  "Network & infrastructure": "🌐",
  "Web application security": "🕸",
  "Vulnerability assessment": "🎯",
  "Exploitation & offensive": "⚡",
  "Post-exploitation & lateral movement": "↔",
  "Cloud & container security": "☁",
  "Identity & access": "🔐",
  "Defensive & blue team": "🛡",
  "Threat intelligence": "📡",
  "Malware & reverse engineering": "🧬",
  "Mobile, IoT & embedded": "📱",
  "Wireless & physical": "📶",
  "Compliance & GRC": "📋",
  "ICS / OT": "🏭",
  "AI / ML security": "🤖",
  "Cryptography & PKI": "🔑",
  "Forensics & incident response": "🧪",
  "Purple team & orchestration": "🟣",
  "Commercial LLM providers": "✦",
};

export function taskCapabilityLabel(task: string): string {
  return TASK_LABELS[task] ?? humanizeToken(task);
}

export function recipeDisplayName(row: Pick<MarketplaceRecipe, "id" | "label">): string {
  return (row.label ?? "").trim() || humanizeToken(row.id);
}

export function recipeCategoryIcon(category?: string): string {
  return CATEGORY_ICONS[category ?? ""] ?? "🛡";
}

export function marketplaceAccessLabel(canRegister?: boolean): string {
  return canRegister ? "Pro deployment" : "Community catalog";
}

export function marketplaceEditionBadge(canRegister?: boolean): string {
  return canRegister ? "Pro Edition" : "Community Edition";
}

export function recipeSummary(row: MarketplaceRecipe): string {
  const tasks = (row.tasks ?? []).map(taskCapabilityLabel).slice(0, 3);
  return [
    row.category,
    row.model ? modelDisplayName(row.model) : null,
    tasks.length ? tasks.join(" · ") : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

export function filterMarketplaceRecipes(
  catalog: MarketplaceRecipe[],
  category: string,
  query: string,
): MarketplaceRecipe[] {
  const q = query.trim().toLowerCase();
  return catalog.filter((row) => {
    if (category && row.category !== category) return false;
    if (!q) return true;
    const blob = [
      row.id,
      row.label,
      row.category,
      row.model,
      row.notes,
      row.license,
      row.base_url_hint,
      ...(row.tasks ?? []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return blob.includes(q);
  });
}

const FEATURE_LABELS: Record<string, { label: string; description: string }> = {
  edition: { label: "Edition", description: "Active packaging tier for this deployment." },
  sso_packaging: {
    label: "Enterprise Sign-In Pack",
    description: "Auth0 and OIDC turnkey SSO packaging.",
  },
  managed_hosting_hooks: {
    label: "Cloud Control Plane",
    description: "Managed hosting hooks and agent pulse integration.",
  },
  scaffold_marketplace: {
    label: "Specialist Exchange",
    description: "Register and deploy custom inference routes.",
  },
  multi_scaffold: {
    label: "Consensus Routing",
    description: "Multi-model planner consensus across routes.",
  },
  blackboard: {
    label: "Mission Brain",
    description: "Shared mission memory across phases.",
  },
  arsenal_wrappers: {
    label: "Tool Arsenal",
    description: "Wrapped offensive and defensive tooling.",
  },
  own_model: {
    label: "Own Model Training",
    description: "Fine-tune and deploy your own Firebreak model.",
  },
};

export type HostingSetupStep = {
  env: string;
  description: string;
  required: boolean;
  satisfied: boolean;
};

export function cloudLinkStatusLabel(enabled?: boolean, controlPlaneUrl?: string | null): string {
  if (!enabled) return "Standby";
  if (!controlPlaneUrl) return "Enabled · awaiting control plane URL";
  return "Linked";
}

export function hostingFeatureRows(features?: Record<string, boolean | string>) {
  if (!features) return [];
  return Object.entries(features)
    .filter(([key]) => key !== "edition")
    .map(([key, value]) => ({
      key,
      label: FEATURE_LABELS[key]?.label ?? humanizeToken(key),
      description: FEATURE_LABELS[key]?.description ?? "Platform capability",
      enabled: Boolean(value),
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

export function hostingSetupSteps(
  edition?: string,
  hosting?: { enabled?: boolean; control_plane_url?: string | null; app_base_url?: string },
): HostingSetupStep[] {
  const isPro = (edition ?? "").toLowerCase() === "pro";
  const managedOn = Boolean(hosting?.enabled);
  const hasControl = Boolean(hosting?.control_plane_url);
  return [
    {
      env: "FIREBREAK_EDITION=pro",
      description: "Upgrade packaging to Pro Edition.",
      required: true,
      satisfied: isPro,
    },
    {
      env: "FIREBREAK_MANAGED_HOSTING=true",
      description: "Enable Cloud Control Plane hooks.",
      required: true,
      satisfied: managedOn,
    },
    {
      env: "FIREBREAK_CONTROL_PLANE_URL=https://control.example",
      description: "Point to your managed control plane endpoint.",
      required: true,
      satisfied: hasControl,
    },
    {
      env: "APP_BASE_URL=https://console.example.com",
      description: "Public URL this agent reports to the control plane.",
      required: false,
      satisfied: Boolean(hosting?.app_base_url),
    },
  ];
}

export function agentPulseSummary(result: {
  ok?: boolean;
  skipped?: boolean;
  reason?: string;
  status?: number;
  error?: string;
}): string {
  if (result.skipped) return result.reason ?? "Agent pulse skipped";
  if (result.ok) return `Control plane acknowledged (${result.status ?? 200})`;
  if (result.error) return result.error;
  if (result.status) return `Control plane returned HTTP ${result.status}`;
  return "Agent pulse failed";
}

export function formatHeartbeatPayload(payload: Record<string, unknown> | undefined): string | null {
  if (!payload) return null;
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
}

export type CorpusPosture = "aggressive" | "defensive" | "balanced" | "";

const POSTURE_LABELS: Record<Exclude<CorpusPosture, "">, string> = {
  aggressive: "Offensive Lens",
  defensive: "Defensive Lens",
  balanced: "Balanced Lens",
};

const POSTURE_HINTS: Record<Exclude<CorpusPosture, "">, string> = {
  aggressive: "Red-team planning, recon phases, and authorized offensive flows.",
  defensive: "Hardening guidance, refusal patterns, and blue-team responses.",
  balanced: "Mixed posture pairs suitable for general mission training.",
};

export function corpusPostureLabel(posture?: string | null): string {
  const key = (posture ?? "").trim().toLowerCase();
  if (key === "aggressive" || key === "defensive" || key === "balanced") {
    return POSTURE_LABELS[key];
  }
  return "All Lenses";
}

export function corpusPostureHint(posture?: string | null): string {
  const key = (posture ?? "").trim().toLowerCase();
  if (key === "aggressive" || key === "defensive" || key === "balanced") {
    return POSTURE_HINTS[key];
  }
  return "Browse every ready-made seed example across offensive, defensive, and balanced lenses.";
}

export function corpusPostureIcon(posture?: string | null): string {
  const key = (posture ?? "").trim().toLowerCase();
  if (key === "aggressive") return "⚡";
  if (key === "defensive") return "🛡";
  if (key === "balanced") return "⚖";
  return "📚";
}

export function corpusLicenseLabel(license?: string | null): string {
  const value = (license ?? "CC-BY-4.0").trim();
  if (value.toUpperCase().includes("CC-BY")) return "Creative Commons · Attribution";
  return value;
}

export type CorpusExample = {
  id: string;
  label: string;
  prompt: string;
  response: string;
  posture?: string;
};

export function filterCorpusExamples(
  examples: CorpusExample[],
  query: string,
): CorpusExample[] {
  const q = query.trim().toLowerCase();
  if (!q) return examples;
  return examples.filter((row) => {
    const blob = [row.id, row.label, row.prompt, row.response, row.posture]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return blob.includes(q);
  });
}

export function corpusExamplePreview(text: string, max = 120): string {
  const trimmed = text.trim().replace(/\s+/g, " ");
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1)}…`;
}

function humanizeToken(value: string): string {
  return value
    .replace(/^w\d+_/i, "")
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
