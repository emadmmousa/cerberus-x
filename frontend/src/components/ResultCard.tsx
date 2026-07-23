import { useState } from "react";
import type { ResultRow } from "../api/client";
import { enrichResultForDisplay } from "../lib/enrichResult";
import {
  isSqlmapInconclusive,
  statusLabel,
  summarizeFinding,
  stripAnsi,
  type FindingSummary,
} from "../lib/summarizeFinding";

function formatTimestamp(ts: string | number): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return String(ts);
  return date.toLocaleString();
}

function rawText(result: unknown): string {
  if (result == null) return "";
  if (typeof result === "string") return stripAnsi(result);
  return JSON.stringify(result, null, 2);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  return value as Record<string, unknown>;
}

type Props = {
  row: ResultRow;
};

export function formatResultBlockForCopy(
  row: ResultRow,
  summary: FindingSummary,
  displayResult: unknown,
  badgeLabel?: string,
): string {
  const lines = [
    summary.title,
    `Status: ${badgeLabel ?? statusLabel(summary.status)}`,
    `Tool: ${row.tool}`,
    `Phase: ${row.phase}`,
    `Target: ${row.target}`,
    `Time: ${formatTimestamp(row.timestamp)}`,
    "",
    "Summary:",
    ...summary.bullets.map((bullet) => `- ${bullet}`),
    "",
    "Technical details:",
    rawText(displayResult),
  ];
  return lines.join("\n");
}

async function copyText(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // fall through to legacy copy
    }
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  document.body.removeChild(textarea);
  return copied;
}

export function ResultCard({ row }: Props) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [copied, setCopied] = useState(false);
  const displayResult = enrichResultForDisplay(row.tool, row.result);
  let summary = summarizeFinding(row.tool, displayResult);
  const payload = asRecord(displayResult);

  if (row.tool === "sqlmap" && isSqlmapInconclusive(displayResult)) {
    const note = typeof payload?.note === "string" ? payload.note.trim() : "";
    summary = {
      ...summary,
      status: "partial",
      bullets: [
        note || "No injectable parameters or forms found — SQLi check inconclusive.",
        payload?.waf_blocked === true
          ? "Target may be WAF/CDN blocked; enable proxy/evasion and crawl deeper."
          : "Try katana/ffuf to discover parameterized endpoints before re-running sqlmap.",
      ],
    };
  }

  const badgeLabel =
    row.tool === "sqlmap" && summary.status === "partial"
      ? "Inconclusive"
      : statusLabel(summary.status);

  const handleCopy = async () => {
    const text = formatResultBlockForCopy(row, summary, displayResult, badgeLabel);
    const ok = await copyText(text);
    if (!ok) return;
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  return (
    <article className={`result-card result-card--${summary.status}`}>
      <header className="result-card__header">
        <span className="result-card__tool">{summary.title}</span>
        <span className={`badge badge--${summary.status === "ok" ? "ok" : summary.status === "failed" ? "err" : "warn"}`}>
          {badgeLabel}
        </span>
        <span className="result-card__meta">{formatTimestamp(row.timestamp)}</span>
        <div className="result-card__actions">
          <button
            type="button"
            className="btn btn--ghost result-card__copy"
            aria-label="Copy full result block"
            onClick={() => void handleCopy()}
          >
            {copied ? "Copied" : "Copy"}
          </button>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? "Hide technical details" : "Show technical details"}
          </button>
        </div>
      </header>
      <ul className="result-card__bullets">
        {summary.bullets.map((b) => (
          <li key={b}>{b}</li>
        ))}
      </ul>
      {showAdvanced && <pre className="pre-block">{rawText(displayResult)}</pre>}
    </article>
  );
}
