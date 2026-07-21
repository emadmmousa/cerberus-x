import { useEffect, useState } from "react";
import { getAuditRecent } from "../api/client";

type AuditEvent = {
  event_type?: string;
  severity?: string;
  timestamp?: string;
  data?: Record<string, unknown>;
};

export function AuditStrip({ disabled = false }: { disabled?: boolean }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (disabled) return;
    let cancelled = false;
    const load = () => {
      getAuditRecent(12)
        .then((data) => {
          if (cancelled) return;
          setEvents((data.events as AuditEvent[]) ?? []);
          setError(null);
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : String(err));
          }
        });
    };
    load();
    const id = window.setInterval(load, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [disabled]);

  const disagreements = events.filter(
    (e) => e.event_type === "AI_SCAFFOLD_DISAGREEMENT",
  ).length;
  const contributes = events.filter(
    (e) => e.event_type === "DATASET_CONTRIBUTE",
  ).length;

  return (
    <div className="arsenal" aria-label="Audit">
      <div className="arsenal__head">
        <div>
          <div className="arsenal__title">Audit</div>
          <p className="arsenal__note">
            {events.length} recent
            {disagreements ? ` · ${disagreements} scaffold disagreements` : ""}
            {contributes ? ` · ${contributes} contributions` : ""}
          </p>
        </div>
      </div>
      {error && <p className="error-text">{error}</p>}
      <ul className="arsenal__list">
        {events.slice(0, 6).map((ev, idx) => (
          <li key={`${ev.event_type}-${ev.timestamp}-${idx}`}>
            <span className="arsenal__name">{ev.event_type ?? "event"}</span>
            <span
              className={`arsenal__mark arsenal__mark--${
                ev.severity === "high" || ev.severity === "critical"
                  ? "missing"
                  : "ready"
              }`}
            >
              {ev.severity ?? "info"}
            </span>
          </li>
        ))}
        {!events.length && !error && (
          <li>
            <span className="arsenal__note">No recent audit events</span>
          </li>
        )}
      </ul>
    </div>
  );
}
