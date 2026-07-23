/** Split operator-facing chat text from hidden thinking/plan blocks. */

import { ensureUtf8Text } from "./textEncoding";

export type ParsedChatMessage = {
  visible: string;
  thinking: string[];
  plans: string[];
};

const PLAN_BLOCK_RE = /```firebreak-plan\s*[\s\S]*?```/gi;
const TOOL_BLOCK_RE = /```firebreak-tool\s*[\s\S]*?```/gi;

function thinkBlockRe(closed: boolean): RegExp {
  const open = String.fromCharCode(60) + "think" + String.fromCharCode(62);
  const close = String.fromCharCode(60) + "/" + "think" + String.fromCharCode(62);
  if (closed) {
    return new RegExp(`${open}([\\s\\S]*?)${close}`, "gi");
  }
  return new RegExp(`${open}[\\s\\S]*$`, "i");
}

export function parseChatMessageContent(raw: string): ParsedChatMessage {
  const thinking: string[] = [];
  const plans: string[] = [];
  let visible = ensureUtf8Text(raw || "");

  visible = visible.replace(PLAN_BLOCK_RE, (block) => {
    plans.push(block.trim());
    return "";
  });
  visible = visible.replace(TOOL_BLOCK_RE, (block) => {
    plans.push(block.trim());
    return "";
  });
  visible = visible.replace(thinkBlockRe(true), (_, inner?: string) => {
    const text = (inner || "").trim();
    if (text) thinking.push(text);
    return "";
  });

  const openThink = visible.match(thinkBlockRe(false));
  if (openThink?.index != null) {
    const hidden = openThink[0]
      .replace(new RegExp(`^${String.fromCharCode(60)}think${String.fromCharCode(62)}`, "i"), "")
      .trim();
    if (hidden) thinking.push(`${hidden}…`);
    visible = visible.slice(0, openThink.index);
  }

  visible = visible.replace(/\n{3,}/g, "\n\n").trim();
  return { visible, thinking, plans };
}

/** Heuristic: long structured planning prose belongs in the collapsed fold, not the thread. */
export function isPlanningVisible(text: string): boolean {
  const trimmed = (text || "").trim();
  if (!trimmed) return false;
  if (/^#{1,3}\s/m.test(trimmed)) return true;
  if (
    /\b(phase plan|seed identification|execution:|recon phase|explanation:|understood\.|let's proceed)\b/i.test(
      trimmed,
    )
  ) {
    return true;
  }
  if (trimmed.length > 220 && /^[\-*\d]/m.test(trimmed)) return true;
  return false;
}

export function visibleChatText(raw: string): string {
  return parseChatMessageContent(raw).visible;
}

export type BriefReplyContext = {
  target?: string;
  needsConfirm?: boolean;
  missionLaunched?: boolean;
  launchError?: string | null;
  osintOnly?: boolean;
  toolProposal?: boolean;
};

const OSINT_TOOL_NAMES = new Set([
  "theharvester",
  "subfinder",
  "gau",
  "sherlock",
  "katana",
  "httpx",
  "whatweb",
  "darkweb",
  "breach_intel",
]);

function extractPlanTarget(plans: string[]): string | undefined {
  for (const block of plans) {
    const match = block.match(/"target"\s*:\s*"([^"]+)"/i);
    if (match?.[1]) return match[1];
  }
  return undefined;
}

export function isOsintToolList(tools: string[] | undefined): boolean {
  if (!tools?.length) return false;
  return tools.every((tool) => OSINT_TOOL_NAMES.has(tool.toLowerCase()));
}

/** One-line operator alert after thinking/planning is folded away. */
export function briefOperatorReply(raw: string, context: BriefReplyContext = {}): string {
  const parsed = parseChatMessageContent(raw);
  const target = context.target || extractPlanTarget(parsed.plans);

  if (context.launchError) {
    return `Launch blocked${target ? ` for ${target}` : ""} — ${context.launchError}`;
  }
  if (context.missionLaunched) {
    return `Mission live${target ? ` on ${target}` : ""}. Track progress in History.`;
  }
  if (context.toolProposal) {
    return "New tool proposal ready — review and approve below.";
  }
  if (context.needsConfirm) {
    if (context.osintOnly) {
      return `OSINT plan ready${target ? ` for ${target}` : ""} — confirm below to run intelligence tools.`;
    }
    return `Strike plan ready${target ? ` for ${target}` : ""} — open Confirm plan below to launch.`;
  }

  const blob = `${raw} ${parsed.thinking.join(" ")}`.toLowerCase();
  if (/\bosint\b|theharvester|breach_intel|darkweb|leak radar|breach vault/.test(blob)) {
    return `OSINT analysis complete${target ? ` for ${target}` : ""} — confirm the next step below.`;
  }
  if (parsed.plans.length || /firebreak-plan/i.test(raw)) {
    return `Plan ready${target ? ` for ${target}` : ""} — confirm below to execute.`;
  }

  return "Analysis complete — expand Thinking... for details or reply to adjust.";
}

export function resolveCollapsedVisibleReply(
  raw: string,
  context: BriefReplyContext | undefined,
): string {
  const parsed = parseChatMessageContent(raw);
  if (parsed.visible && !isPlanningVisible(parsed.visible) && parsed.visible.length <= 240) {
    return parsed.visible;
  }

  const hasFoldedContent =
    isPlanningVisible(parsed.visible) ||
    parsed.thinking.length > 0 ||
    parsed.plans.length > 0;

  if (!hasFoldedContent) {
    return parsed.visible;
  }

  return briefOperatorReply(raw, context);
}
