import { useEffect, useState } from "react";
import { getBlackboard } from "../api/client";

type BbEntry = {
  key?: string;
  value?: unknown;
  version?: number;
};

type Props = {
  missionId?: string | null;
  disabled?: boolean;
};

export function BlackboardPanel({ missionId, disabled = false }: Props) {
  const [items, setItems] = useState<BbEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!missionId || disabled) {
      setItems([]);
      return;
    }
    let cancelled = false;
    const load = () => {
      getBlackboard(missionId)
        .then((data) => {
          if (cancelled) return;
          setItems((data.items as BbEntry[]) ?? []);
          setError(null);
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : String(err));
          }
        });
    };
    load();
    const id = window.setInterval(load, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [missionId, disabled]);

  if (!missionId) {
    return (
      <div className="arsenal" aria-label="Blackboard">
        <div className="arsenal__head">
          <div className="arsenal__title">Blackboard</div>
          <p className="arsenal__note">Launch a mission to see shared findings</p>
        </div>
      </div>
    );
  }

  const findings = items.find((i) => i.key === "findings");
  const proposed = items.find((i) => i.key === "proposed_action");
  const hardening = items.find((i) => i.key === "hardening");
  const summary = items.find((i) => i.key === "findings.summary");
  const consensus = items.find((i) => i.key === "consensus");
  const consensusVal =
    consensus &&
    typeof consensus.value === "object" &&
    consensus.value !== null
      ? (consensus.value as {
          confidence?: number;
          mode?: string;
          sources?: string[];
        })
      : null;
  const latest =
    findings &&
    typeof findings.value === "object" &&
    findings.value !== null &&
    "latest" in (findings.value as Record<string, unknown>)
      ? ((findings.value as { latest?: Array<{ tool?: string; ports?: number; error?: string }> })
          .latest ?? [])
      : [];

  const proposedCount =
    proposed &&
    typeof proposed.value === "object" &&
    proposed.value !== null &&
    "count" in (proposed.value as Record<string, unknown>)
      ? Number((proposed.value as { count?: number }).count ?? 0)
      : null;

  const hardenCount =
    hardening &&
    typeof hardening.value === "object" &&
    hardening.value !== null &&
    "recommendations" in (hardening.value as Record<string, unknown>)
      ? ((hardening.value as { recommendations?: unknown[] }).recommendations ?? [])
          .length
      : null;

  return (
    <div className="arsenal" aria-label="Blackboard">
      <div className="arsenal__head">
        <div>
          <div className="arsenal__title">Blackboard</div>
          <p className="arsenal__note">
            {items.length} keys · mission {missionId.slice(0, 8)}
            {proposedCount != null ? ` · ${proposedCount} proposed` : ""}
            {hardenCount != null ? ` · ${hardenCount} hardening` : ""}
            {consensusVal?.confidence != null
              ? ` · consensus ${(consensusVal.confidence * 100).toFixed(0)}%`
              : ""}
          </p>
        </div>
      </div>
      {error && <p className="error-text">{error}</p>}
      <ul className="arsenal__list">
        {consensusVal && (
          <li>
            <span className="arsenal__name">consensus</span>
            <span className="arsenal__mark arsenal__mark--ready">
              {consensusVal.mode ?? "n/a"}
              {consensusVal.confidence != null
                ? ` ${(consensusVal.confidence * 100).toFixed(0)}%`
                : ""}
            </span>
          </li>
        )}
        {proposed && (
          <li>
            <span className="arsenal__name">proposed_action</span>
            <span className="arsenal__mark arsenal__mark--ready">
              {proposedCount ?? "v" + (proposed.version ?? 1)}
            </span>
          </li>
        )}
        {hardening && (
          <li>
            <span className="arsenal__name">hardening</span>
            <span className="arsenal__mark arsenal__mark--ready">
              {hardenCount ?? 0} recs
            </span>
          </li>
        )}
        {summary && (
          <li>
            <span className="arsenal__name">findings.summary</span>
            <span className="arsenal__mark arsenal__mark--ready">
              v{summary.version ?? 1}
            </span>
          </li>
        )}
        {latest.map((row, idx) => (
          <li key={`${row.tool}-${idx}`}>
            <span className="arsenal__name">{row.tool ?? "tool"}</span>
            <span className="arsenal__mark arsenal__mark--ready">
              {row.error
                ? "err"
                : row.ports != null
                  ? `${row.ports} ports`
                  : "ok"}
            </span>
          </li>
        ))}
        {!latest.length &&
          !proposed &&
          !hardening &&
          items.slice(0, 6).map((entry) => (
            <li key={entry.key}>
              <span className="arsenal__name">{entry.key}</span>
              <span className="arsenal__mark arsenal__mark--ready">v{entry.version ?? 1}</span>
            </li>
          ))}
        {!items.length && !error && (
          <li>
            <span className="arsenal__note">No blackboard entries yet</span>
          </li>
        )}
      </ul>
    </div>
  );
}
