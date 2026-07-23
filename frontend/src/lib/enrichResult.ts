import { isSqlmapInconclusive } from "./summarizeFinding";
import { sanitizeBreachResultForDisplay } from "./sanitizeBreachResult";

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  return value as Record<string, unknown>;
}

/** Normalize API payloads and add display flags for legacy sqlmap rows. */
export function enrichResultForDisplay(tool: string, result: unknown): unknown {
  let payload = result;
  if (typeof payload === "string") {
    try {
      payload = JSON.parse(payload) as unknown;
    } catch {
      return result;
    }
  }

  const obj = asRecord(payload);
  if (!obj) return result;

  const nested = asRecord(obj.result);
  if (nested && !obj.raw_output && nested.raw_output) {
    return enrichResultForDisplay(tool, nested);
  }

  const name = (tool || String(obj.tool || "")).trim().toLowerCase();
  if (name === "breach_intel") {
    return sanitizeBreachResultForDisplay(obj);
  }
  if (name !== "sqlmap" || obj.vulnerable === true) {
    return obj;
  }

  if (!isSqlmapInconclusive(obj)) {
    return obj;
  }

  const raw = typeof obj.raw_output === "string" ? obj.raw_output : "";
  const crawlOnly =
    /searching for links with depth/i.test(raw) &&
    !/testing if the target url/i.test(raw);

  return {
    ...obj,
    partial: true,
    no_injection_surface: true,
    note:
      (typeof obj.note === "string" && obj.note.trim()) ||
      (crawlOnly
        ? "Crawler finished but sqlmap never reached an injectable parameter — SQLi check inconclusive."
        : "No injectable GET parameters or forms found — SQLi check inconclusive."),
  };
}
