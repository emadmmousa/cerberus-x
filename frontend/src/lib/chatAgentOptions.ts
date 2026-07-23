import type { OsintSeed } from "./osintTargets";

export type ChatPosture = "aggressive" | "balanced" | "defensive";

export type ChatAttachment = {
  name: string;
  content: string;
  type: string;
};

export type ChatAgentOptions = {
  deepThink: boolean;
  webSearch: boolean;
  useProxy: boolean;
  proxyProtocol: "http" | "https" | "socks5h";
  model: string;
  posture: ChatPosture;
  attachments: ChatAttachment[];
  osintSeeds: OsintSeed[];
  // Auto Run: a ready plan may auto-launch on execute intent (default on).
  autoRun: boolean;
  // Always Run: auto-launch even plan-only ready proposals (default off).
  alwaysRun: boolean;
  // Creative mode: ChatGPT-style conversational agent (default on).
  creativeMode: boolean;
};

export type ChatAgentConfig = {
  llm_configured: boolean;
  llm_reachable?: boolean;
  models: { id: string; label: string }[];
  default_model: string;
  postures: { id: ChatPosture; label: string; power: number }[];
  defaults: {
    deep_think: boolean;
    web_search: boolean;
    posture: ChatPosture;
    model: string;
  };
  attachment_limits: { max_files: number; max_bytes: number };
};

const STORAGE_KEY = "firebreak:chatAgentOptions";

export const DEFAULT_CHAT_OPTIONS: ChatAgentOptions = {
  deepThink: true,
  webSearch: false,
  useProxy: true,
  proxyProtocol: "http",
  model: "",
  posture: "aggressive",
  attachments: [],
  osintSeeds: [],
  autoRun: true,
  alwaysRun: false,
  creativeMode: true,
};

export function loadChatOptions(): ChatAgentOptions {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_CHAT_OPTIONS };
    const parsed = JSON.parse(raw) as Partial<ChatAgentOptions>;
    return {
      ...DEFAULT_CHAT_OPTIONS,
      ...parsed,
      attachments: [],
      osintSeeds: Array.isArray(parsed.osintSeeds) ? parsed.osintSeeds : [],
      useProxy: parsed.useProxy ?? DEFAULT_CHAT_OPTIONS.useProxy,
      proxyProtocol:
        parsed.proxyProtocol === "https" || parsed.proxyProtocol === "socks5h"
          ? parsed.proxyProtocol
          : "http",
      autoRun: parsed.autoRun ?? DEFAULT_CHAT_OPTIONS.autoRun,
      alwaysRun: parsed.alwaysRun ?? DEFAULT_CHAT_OPTIONS.alwaysRun,
      creativeMode: parsed.creativeMode ?? DEFAULT_CHAT_OPTIONS.creativeMode,
    };
  } catch {
    return { ...DEFAULT_CHAT_OPTIONS };
  }
}

export function saveChatOptions(opts: ChatAgentOptions): void {
  const { attachments: _, ...persist } = opts;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(persist));
}

export function toApiOptions(opts: ChatAgentOptions) {
  return {
    deep_think: opts.deepThink,
    web_search: opts.webSearch,
    use_proxy: opts.useProxy,
    proxy_protocol: opts.proxyProtocol,
    auto_run: opts.autoRun,
    always_run: opts.alwaysRun,
    creative_mode: opts.creativeMode,
    model: opts.model || undefined,
    posture: opts.posture,
    attachments: opts.attachments.map((a) => ({
      name: a.name,
      content: a.content,
      type: a.type,
    })),
    osint_seeds: opts.osintSeeds.map((seed) => ({
      kind: seed.kind,
      value: seed.value,
      display: seed.display,
    })),
  };
}

export const POSTURE_LABELS: Record<ChatPosture, string> = {
  aggressive: "Max",
  balanced: "Bal",
  defensive: "Def",
};
