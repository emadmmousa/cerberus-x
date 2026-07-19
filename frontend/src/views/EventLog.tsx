import { useEventLog } from "../hooks/useEventLog";

function formatTime(ts?: number): string {
  if (!ts) return new Date().toLocaleTimeString();
  return new Date(ts * 1000).toLocaleTimeString();
}

export function EventLog() {
  const { entries, levelFilter, setLevelFilter, textFilter, setTextFilter } =
    useEventLog();

  return (
    <div>
      <h2>Event Log</h2>
      <div className="panel">
        <div className="row">
          <div className="field" style={{ maxWidth: 160 }}>
            <label htmlFor="log-level">Level</label>
            <select
              id="log-level"
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value)}
            >
              <option value="">All</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="log-filter">Filter (e.g. proxy_skipped)</label>
            <input
              id="log-filter"
              type="search"
              placeholder="substring filter"
              value={textFilter}
              onChange={(e) => setTextFilter(e.target.value)}
            />
          </div>
        </div>
        <div className="scroll-box scroll-box--tall">
          {entries.length === 0 && (
            <p className="result-card__meta">Waiting for events…</p>
          )}
          {entries.map((entry) => (
            <div
              key={entry.id}
              className={`log-entry log-entry--${entry.level ?? "INFO"}`}
            >
              [{formatTime(entry.timestamp)}] {entry.level}: {entry.message}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
