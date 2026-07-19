import { useState } from "react";
import type { ResultRow } from "../api/client";
import {
  statusLabel,
  summarizeFinding,
  stripAnsi,
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

type Props = {
  row: ResultRow;
};

export function ResultCard({ row }: Props) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const summary = summarizeFinding(row.tool, row.result);

  return (
    <article className={`result-card result-card--${summary.status}`}>
      <header className="result-card__header">
        <span className="result-card__tool">{summary.title}</span>
        <span className={`badge badge--${summary.status === "ok" ? "ok" : summary.status === "failed" ? "err" : "warn"}`}>
          {statusLabel(summary.status)}
        </span>
        <span className="result-card__meta">{formatTimestamp(row.timestamp)}</span>
        <button
          type="button"
          className="btn"
          style={{ marginLeft: "auto", padding: "0.25rem 0.5rem" }}
          onClick={() => setShowAdvanced((v) => !v)}
        >
          {showAdvanced ? "Hide technical details" : "Show technical details"}
        </button>
      </header>
      <ul className="result-card__bullets">
        {summary.bullets.map((b) => (
          <li key={b}>{b}</li>
        ))}
      </ul>
      {showAdvanced && <pre className="pre-block">{rawText(row.result)}</pre>}
    </article>
  );
}
