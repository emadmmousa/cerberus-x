import { useState } from "react";
import type { PhaseView } from "../hooks/useMission";
import { PHASE_LABELS } from "../lib/summarizeFinding";
import { ResultCard } from "./ResultCard";

const STATE_LABEL: Record<PhaseView["state"], string> = {
  pending: "Queued",
  running: "Running",
  done: "Complete",
  failed: "Failed",
  skipped: "Skipped",
};

type Props = {
  phase: PhaseView;
  index: number;
};

export function PhaseCard({ phase, index }: Props) {
  const [open, setOpen] = useState(false);
  const hasResults = phase.findings.length > 0;
  const label = PHASE_LABELS[phase.name] ?? phase.name.replace(/_/g, " ");

  return (
    <div className={`phase-card phase-card--${phase.state}`}>
      <div className="phase-card__rail">
        <span className="phase-card__node" />
      </div>
      <div className="phase-card__body">
        <button
          type="button"
          className="phase-card__head"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          <span className="phase-card__index">
            {String(index + 1).padStart(2, "0")}
          </span>
          <span className="phase-card__name">{label}</span>
          <span className={`phase-card__state phase-card__state--${phase.state}`}>
            {STATE_LABEL[phase.state]}
          </span>
          {phase.parallel && <span className="badge">parallel</span>}
          {hasResults && (
            <span className="badge badge--ok">
              {phase.findings.length} result{phase.findings.length === 1 ? "" : "s"}
            </span>
          )}
          <span className="phase-card__chevron">{open ? "\u2212" : "+"}</span>
        </button>

        <div className="phase-card__tools">
          {phase.tools.map((tool) => (
            <span key={tool} className="chip">
              {tool}
            </span>
          ))}
        </div>

        {phase.error && phase.state !== "skipped" && (
          <p className="error-text">{phase.error}</p>
        )}
        {phase.when && phase.state === "skipped" && (
          <p className="phase-card__cond">Skipped based on earlier results.</p>
        )}

        {open && (
          <div className="phase-card__findings">
            {hasResults ? (
              phase.findings.map((row, i) => (
                <ResultCard key={`${row.tool}-${row.timestamp}-${i}`} row={row} />
              ))
            ) : (
              <p className="result-card__meta">
                {phase.state === "running"
                  ? "Collecting results\u2026"
                  : "No results recorded for this step yet."}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
