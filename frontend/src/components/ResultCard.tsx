import { useState } from "react";
import type { ResultRow } from "../api/client";

function formatTimestamp(ts: string | number): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return String(ts);
  return date.toLocaleString();
}

function extractBody(result: unknown): string {
  if (result == null) return "";
  if (typeof result === "string") return result;
  if (typeof result === "object") {
    const obj = result as Record<string, unknown>;
    for (const key of ["output", "stdout", "stderr", "message", "data"]) {
      if (typeof obj[key] === "string") return obj[key] as string;
    }
  }
  return JSON.stringify(result, null, 2);
}

type Props = {
  row: ResultRow;
};

export function ResultCard({ row }: Props) {
  const [showRaw, setShowRaw] = useState(false);
  const body = extractBody(row.result);

  return (
    <article className="result-card">
      <header className="result-card__header">
        <span className="result-card__tool">{row.tool}</span>
        <span className="badge">{row.phase}</span>
        <span className="result-card__meta">{formatTimestamp(row.timestamp)}</span>
        <button
          type="button"
          className="btn"
          style={{ marginLeft: "auto", padding: "0.25rem 0.5rem" }}
          onClick={() => setShowRaw((v) => !v)}
        >
          {showRaw ? "Hide JSON" : "Raw JSON"}
        </button>
      </header>
      {showRaw ? (
        <pre className="pre-block">{JSON.stringify(row.result, null, 2)}</pre>
      ) : (
        <pre className="pre-block">{body}</pre>
      )}
    </article>
  );
}
