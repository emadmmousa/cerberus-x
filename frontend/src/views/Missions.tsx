import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  listMissions,
  type MissionProposal,
  type MissionSummaryRow,
} from "../api/client";
import { ManualMissionForm, type ManualMissionPrefill } from "../components/ManualMissionForm";
import { MissionChat } from "../components/MissionChat";
import { useAuth } from "../providers/AuthProvider";

function statusModifier(state?: string): string {
  const s = (state ?? "").toUpperCase();
  if (s === "SUCCESS") return "success";
  if (s === "FAILURE") return "failure";
  if (s === "STARTED" || s === "PROGRESS" || s === "RETRY" || s === "PENDING")
    return "running";
  return "pending";
}

type Mode = "chat" | "manual";

export function Missions() {
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const mode: Mode = params.get("mode") === "manual" ? "manual" : "chat";
  const [rows, setRows] = useState<MissionSummaryRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [prefill, setPrefill] = useState<ManualMissionPrefill | null>(null);

  const loadRail = useCallback(() => {
    listMissions()
      .then((data) => setRows(data.missions ?? []))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadRail();
    const t = window.setInterval(loadRail, 8000);
    return () => window.clearInterval(t);
  }, [loadRail]);

  function setMode(next: Mode) {
    const sp = new URLSearchParams(params);
    if (next === "manual") sp.set("mode", "manual");
    else sp.delete("mode");
    setParams(sp, { replace: true });
  }

  function editManual(proposal: MissionProposal) {
    setPrefill({
      target: proposal.target,
      posture: (proposal.posture as ManualMissionPrefill["posture"]) || "balanced",
      nl_goal: proposal.nl_goal,
      stealth: (proposal.stealth as ManualMissionPrefill["stealth"]) || "high",
      ai_mode: true,
    });
    setMode("manual");
  }

  return (
    <div className="missions-home">
      <aside className="missions-rail panel" aria-label="Mission history">
        <div className="page-head">
          <div className="page-head__text">
            <div className="section-label">Missions</div>
            <p className="section-sub">Org history</p>
          </div>
        </div>
        {error && <p className="error-text">{error}</p>}
        {loading ? (
          <p className="empty-state">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="empty-state">No missions yet.</p>
        ) : (
          <ul className="mission-cards mission-cards--rail">
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
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <div className="missions-main">
        {can("operator") && (
          <div className="panel missions-mode" role="tablist" aria-label="Mission mode">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "chat"}
              className={`admin-tab${mode === "chat" ? " admin-tab--active" : ""}`}
              onClick={() => setMode("chat")}
            >
              Chat
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "manual"}
              className={`admin-tab${mode === "manual" ? " admin-tab--active" : ""}`}
              onClick={() => setMode("manual")}
            >
              Manual
            </button>
          </div>
        )}

        {can("operator") ? (
          mode === "chat" ? (
            <MissionChat
              onMissionLaunched={loadRail}
              onEditManual={editManual}
            />
          ) : (
            <ManualMissionForm
              prefill={prefill}
              navigateOnLaunch={false}
              onLaunched={() => {
                setPrefill(null);
                loadRail();
                setMode("chat");
              }}
            />
          )
        ) : (
          <section className="panel">
            <div className="section-label">View only</div>
            <p className="section-sub">
              Operator role required to chat or launch missions.
            </p>
          </section>
        )}
      </div>
    </div>
  );
}
