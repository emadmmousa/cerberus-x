/** Redact internal breach provider names from mission result payloads. */

import {
  BREACH_VAULT_PRODUCT,
  LEAK_RADAR_PRODUCT,
} from "./breachIntelBranding";

const INTERNAL_NAME_RE = /\b(dehashed|leakcheck)\b/gi;

function rewriteKeys(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(rewriteKeys);
  }
  if (!value || typeof value !== "object") {
    if (typeof value === "string") {
      return value.replace(/\bdehashed\b/gi, BREACH_VAULT_PRODUCT).replace(/\bleakcheck\b/gi, LEAK_RADAR_PRODUCT);
    }
    return value;
  }

  const row = value as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  for (const [key, child] of Object.entries(row)) {
    let nextKey = key;
    if (key === "dehashed") nextKey = "breach_vault";
    if (key === "leakcheck") nextKey = "leak_radar";
    if (key === "dehashed_databases") nextKey = "breach_vault_databases";
    if (key === "leakcheck_sources") nextKey = "leak_radar_sources";
    if (key === "dehashed_hits") nextKey = "breach_vault_hits";
    if (key === "leakcheck_hits") nextKey = "leak_radar_hits";
    if (key === "provider" && typeof child === "string") {
      out.product =
        child.toLowerCase() === "leakcheck" ? LEAK_RADAR_PRODUCT : BREACH_VAULT_PRODUCT;
      continue;
    }
    out[nextKey] = rewriteKeys(child);
  }
  return out;
}

export function sanitizeBreachResultForDisplay(result: unknown): unknown {
  if (result == null) return result;
  if (typeof result === "string") {
    return result.replace(INTERNAL_NAME_RE, (match) =>
      match.toLowerCase() === "leakcheck" ? LEAK_RADAR_PRODUCT : BREACH_VAULT_PRODUCT,
    );
  }
  return rewriteKeys(result);
}
