import type { ReactNode } from "react";
import type { WorkerReadiness } from "../api/client";

type Mode = "chat" | "prompts" | "manual";

type Props = {
  mode: Mode;
  onModeChange: (mode: Mode) => void;
  canOperate: boolean;
  activeCount: number;
  totalCount: number;
  doneCount: number;
  failedCount: number;
  loading: boolean;
  railOpen: boolean;
  onRailToggle: () => void;
  onNewChat?: () => void;
  error?: string | null;
  workerReadiness?: WorkerReadiness;
  extra?: ReactNode;
};

export function WorkerReadinessChip({
  readiness,
}: {
  readiness: WorkerReadiness;
}) {
  const message =
    readiness.message ||
    (readiness.status === "unreachable"
      ? "Worker readiness is unknown. Verify the API, broker, and worker connectivity."
      : "Worker readiness details are unavailable.");
  const label =
    readiness.status === "ready"
      ? "Workers ready"
      : readiness.status === "stale"
        ? "Workers stale"
        : "Workers unreachable";

  return (
    <details className={`ops-worker ops-worker--${readiness.status}`}>
      <summary className="ops-bar__action">{label}</summary>
      <div className="ops-worker__detail">
        <p>{message}</p>
        {readiness.missing_tasks.length > 0 && (
          <p>
            Missing tasks: <span>{readiness.missing_tasks.join(", ")}</span>
          </p>
        )}
      </div>
    </details>
  );
}

export function OperationsCommandBar({
  mode,
  onModeChange,
  canOperate,
  activeCount,
  totalCount,
  doneCount,
  failedCount,
  loading,
  railOpen,
  onRailToggle,
  onNewChat,
  error,
  workerReadiness,
  extra,
}: Props) {
  const statusLabel =
    activeCount > 0
      ? `${activeCount} live`
      : loading
        ? "Syncing"
        : totalCount > 0
          ? "Standby"
          : "Ready";

  const statusTone =
    activeCount > 0 ? "live" : error ? "error" : totalCount > 0 ? "idle" : "ready";

  return (
    <header className="ops-bar" aria-label="Operations command bar">
      <div className="ops-bar__brand">
        <span className={`ops-bar__pulse ops-bar__pulse--${statusTone}`} aria-hidden="true" />
        <div className="ops-bar__titles">
          <h1 className="ops-bar__title">Operations</h1>
          <p className="ops-bar__status">
            {statusLabel}
            {totalCount > 0 && (
              <>
                {" · "}
                {totalCount} total · {doneCount} done
                {failedCount > 0 ? ` · ${failedCount} failed` : ""}
              </>
            )}
          </p>
        </div>
      </div>

      {canOperate && (
        <div className="ops-bar__modes" role="tablist" aria-label="Mission mode">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "chat"}
            className={`ops-bar__mode${mode === "chat" ? " ops-bar__mode--active" : ""}`}
            onClick={() => onModeChange("chat")}
          >
            Agent
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "prompts"}
            className={`ops-bar__mode${mode === "prompts" ? " ops-bar__mode--active" : ""}`}
            onClick={() => onModeChange("prompts")}
          >
            Prompts
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "manual"}
            className={`ops-bar__mode${mode === "manual" ? " ops-bar__mode--active" : ""}`}
            onClick={() => onModeChange("manual")}
          >
            Manual
          </button>
        </div>
      )}

      <div className="ops-bar__actions">
        {extra}
        {workerReadiness && <WorkerReadinessChip readiness={workerReadiness} />}
        {canOperate && mode === "chat" && onNewChat && (
          <button type="button" className="ops-bar__action" onClick={onNewChat}>
            New chat
          </button>
        )}
        <button
          type="button"
          className={`ops-bar__action ops-bar__action--history${railOpen ? " ops-bar__action--on" : ""}`}
          aria-expanded={railOpen}
          aria-controls="missions-rail-drawer"
          onClick={onRailToggle}
        >
          History
          {totalCount > 0 && <span className="ops-bar__badge">{totalCount}</span>}
        </button>
      </div>

      {error && <p className="ops-bar__error">{error}</p>}
    </header>
  );
}
