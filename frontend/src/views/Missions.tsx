import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listMissions, type MissionSummaryRow } from "../api/client";
import { useAuth } from "../providers/AuthProvider";

function statusModifier(state?: string): string {
  const s = (state ?? "").toUpperCase();
  if (s === "SUCCESS") return "success";
  if (s === "FAILURE") return "failure";
  if (s === "STARTED" || s === "PROGRESS" || s === "RETRY") return "running";
  return "pending";
}

export function Missions() {
  const { can } = useAuth();
  const [rows, setRows] = useState<MissionSummaryRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    listMissions()
      .then((data) => {
        if (!cancelled) setRows(data.missions ?? []);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mission">
      <section className="panel" aria-label="Missions">
        <div className="page-head">
          <div className="page-head__text">
            <div className="section-label">Missions</div>
            <p className="section-sub">Org-scoped runs from this session.</p>
          </div>
          {can("operator") && (
            <Link to="/missions/new" className="btn btn--primary">
              New mission
            </Link>
          )}
        </div>
        {error && <p className="error-text">{error}</p>}
      </section>

      <section className="panel" aria-label="Mission list">
        {loading ? (
          <p className="empty-state">Loading missions…</p>
        ) : rows.length === 0 ? (
          <p className="empty-state">No missions yet. Launch one to get started.</p>
        ) : (
          <ul className="mission-cards">
            {rows.map((m) => (
              <li key={m.task_id}>
                <Link to={`/missions/${m.task_id}`} className="mission-card">
                  <span
                    className={`mission-card__status mission-card__status--${statusModifier(m.state)}`}
                    aria-hidden="true"
                  />
                  <div className="mission-card__body">
                    <div className="mission-card__target">
                      {m.target || m.task_id}
                    </div>
                    {(m.nl_goal || m.error) && (
                      <div className="mission-card__goal">
                        {m.error || m.nl_goal}
                      </div>
                    )}
                  </div>
                  <div className="mission-card__meta">
                    {m.posture && <span className="chip">{m.posture}</span>}
                    {m.ai_mode && <span className="badge badge--ok">AI</span>}
                    <span className="mission-card__state">{m.state ?? "—"}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
