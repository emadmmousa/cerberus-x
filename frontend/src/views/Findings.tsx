import { useCallback, useEffect, useState } from "react";
import { getResults, type ResultRow } from "../api/client";
import { ResultCard } from "../components/ResultCard";

type Props = {
  target: string;
  onTargetChange: (target: string) => void;
};

export function Findings({ target, onTargetChange }: Props) {
  const [rows, setRows] = useState<ResultRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!target.trim()) {
      setRows([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await getResults(target.trim());
      setRows(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [target]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <h2>Findings</h2>
      <div className="panel">
        <div className="row">
          <div className="field">
            <label htmlFor="findings-target">Target</label>
            <input
              id="findings-target"
              type="text"
              placeholder="example.com"
              value={target}
              onChange={(e) => onTargetChange(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => void load()}
            disabled={loading || !target.trim()}
          >
            Refresh
          </button>
        </div>
        {error && <p className="error-text">{error}</p>}
        {loading && <p className="result-card__meta">Loading…</p>}
        {!loading && rows.length === 0 && target.trim() && (
          <p className="result-card__meta">No results for this target.</p>
        )}
        {rows.map((row, index) => (
          <ResultCard key={`${row.tool}-${row.timestamp}-${index}`} row={row} />
        ))}
      </div>
    </div>
  );
}
