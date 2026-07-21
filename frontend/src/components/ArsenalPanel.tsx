import { useCallback, useEffect, useState } from "react";
import {
  getToolsCatalog,
  getToolsHealth,
  type ToolCatalogEntry,
} from "../api/client";

type HealthRow = {
  name: string;
  ready: boolean;
  status: string;
  detail?: string;
};

export function ArsenalPanel({ disabled = false }: { disabled?: boolean }) {
  const [tools, setTools] = useState<ToolCatalogEntry[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [health, setHealth] = useState<Record<string, HealthRow>>({});
  const [summary, setSummary] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getToolsCatalog()
      .then((data) => {
        if (cancelled) return;
        setTools(data.tools ?? []);
        setNote(data.note ?? null);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const probe = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      let poll = await getToolsHealth();
      const taskId = poll.task_id;
      for (let i = 0; i < 40; i += 1) {
        if (poll.state === "SUCCESS" && poll.result) break;
        if (poll.state === "FAILURE") {
          throw new Error(poll.error || "tool health probe failed");
        }
        await new Promise((r) => setTimeout(r, 400));
        poll = await getToolsHealth(taskId);
      }
      if (!poll.result) {
        throw new Error("tool health probe timed out");
      }
      const map: Record<string, HealthRow> = {};
      for (const row of poll.result.tools) {
        map[row.name] = {
          name: row.name,
          ready: row.ready,
          status: row.status,
          detail: row.detail,
        };
      }
      setHealth(map);
      setSummary(`${poll.result.ready}/${poll.result.count} ready on workers`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  const byCategory = tools.reduce<Record<string, ToolCatalogEntry[]>>(
    (acc, tool) => {
      const key = tool.category || "other";
      (acc[key] ??= []).push(tool);
      return acc;
    },
    {},
  );

  return (
    <div className="arsenal" aria-label="Tool arsenal">
      <div className="arsenal__head">
        <div>
          <div className="arsenal__title">Arsenal ({tools.length} wrappers)</div>
          {note && <p className="arsenal__note">{note}</p>}
          {summary && <p className="arsenal__summary">{summary}</p>}
        </div>
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => void probe()}
          disabled={disabled || busy}
        >
          {busy ? "Probing…" : "Probe workers"}
        </button>
      </div>
      {error && <p className="error-text">{error}</p>}
      <div className="arsenal__grid">
        {Object.entries(byCategory).map(([category, rows]) => (
          <div key={category} className="arsenal__group">
            <div className="arsenal__cat">{category.replace(/_/g, " ")}</div>
            <ul className="arsenal__list">
              {rows.map((tool) => {
                const h = health[tool.name];
                const mark = h
                  ? h.ready
                    ? "ready"
                    : "missing"
                  : tool.maturity;
                return (
                  <li key={tool.name} title={h?.detail || tool.description}>
                    <span className="arsenal__name">{tool.name}</span>
                    <span className={`arsenal__mark arsenal__mark--${mark}`}>
                      {mark}
                    </span>
                    {tool.risk === "high" && (
                      <span className="arsenal__risk">high</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
