import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { MissionSummaryRow } from "../api/client";
import { usePagination } from "../hooks/usePagination";
import {
  filterMissions,
  missionPostureLabel,
  missionStateLabel,
  missionStats,
  missionStatusKind,
  shortTaskId,
  type MissionFilter,
} from "../lib/missionSummary";
import { ListPagination } from "./ListPagination";
import { SkeletonRows } from "./PageLoader";

type Props = {
  rows: MissionSummaryRow[];
  loading: boolean;
  error: string | null;
  onRefresh?: () => void;
  className?: string;
  id?: string;
};

const FILTERS: { id: MissionFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "done", label: "Done" },
  { id: "failed", label: "Failed" },
];

export function MissionRail({
  rows,
  loading,
  error,
  onRefresh,
  className = "",
  id,
}: Props) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<MissionFilter>("all");

  const stats = useMemo(() => missionStats(rows), [rows]);
  const filtered = useMemo(
    () => filterMissions(rows, query, filter),
    [rows, query, filter],
  );
  const missionsPage = usePagination(filtered, {
    pageSize: 8,
    pageSizeOptions: [8, 16, 32],
    resetKey: `${query}|${filter}`,
  });

  function filterCount(id: MissionFilter): number {
    if (id === "all") return stats.total;
    if (id === "active") return stats.active;
    if (id === "done") return stats.done;
    return stats.failed;
  }

  return (
    <aside
      id={id}
      className={`missions-rail panel missions-rail--enhanced ${className}`.trim()}
      aria-label="Mission history"
    >
      <div className="missions-rail__head">
        <div className="missions-rail__title-block">
          <div className="section-label">Mission history</div>
          <p className="missions-rail__subtitle">
            {stats.active > 0
              ? `${stats.active} running now`
              : `${stats.total} recorded mission${stats.total === 1 ? "" : "s"}`}
          </p>
        </div>
        {onRefresh && (
          <button
            type="button"
            className="btn btn--ghost btn--sm missions-rail__refresh"
            aria-label="Refresh mission list"
            onClick={onRefresh}
          >
            Refresh
          </button>
        )}
      </div>

      <div className="missions-rail__toolbar">
        <label className="sr-only" htmlFor="mission-rail-search">
          Search missions
        </label>
        <input
          id="mission-rail-search"
          type="search"
          className="missions-rail__input"
          placeholder="Search target or goal…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoComplete="off"
        />
        <div className="missions-filters" role="tablist" aria-label="Filter missions">
          {FILTERS.map((item) => {
            const count = filterCount(item.id);
            return (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={filter === item.id}
                className={`missions-filter${filter === item.id ? " missions-filter--active" : ""}`}
                onClick={() => setFilter(item.id)}
              >
                {item.label}
                {count > 0 && <span className="missions-filter__count">{count}</span>}
              </button>
            );
          })}
        </div>
      </div>

      {error && <p className="error-text missions-rail__error">{error}</p>}

      <div className="missions-rail__list">
        {loading ? (
          <SkeletonRows count={5} />
        ) : filtered.length === 0 ? (
          <div className="missions-empty">
            <p className="missions-empty__title">
              {rows.length === 0 ? "No missions yet" : "No matches"}
            </p>
            <p className="missions-empty__hint">
              {rows.length === 0
                ? "Launch from the agent to populate history."
                : "Try another filter or search term."}
            </p>
          </div>
        ) : (
          <>
            <ul className="mission-cards mission-cards--rail">
              {missionsPage.items.map((m) => {
                const kind = missionStatusKind(m.state);
                const goal = (m.error || m.nl_goal || "").trim();
                return (
                  <li key={m.task_id}>
                    <Link to={`/missions/${m.task_id}`} className="mission-card mission-card--rail">
                      <span
                        className={`mission-card__status mission-card__status--${kind}`}
                        aria-hidden="true"
                      />
                      <div className="mission-card__body">
                        <div className="mission-card__row">
                          <span className="mission-card__target">
                            {m.target || shortTaskId(m.task_id)}
                          </span>
                          <span className={`mission-card__state mission-card__state--${kind}`}>
                            {missionStateLabel(m.state)}
                          </span>
                        </div>
                        {goal && <div className="mission-card__goal">{goal}</div>}
                        <div className="mission-card__foot">
                          <span className="mission-card__id mono">{shortTaskId(m.task_id)}</span>
                          <div className="mission-card__meta">
                            {m.posture && (
                              <span className="chip chip--sm">{missionPostureLabel(m.posture)}</span>
                            )}
                            {m.ai_mode && <span className="badge badge--ok">AI</span>}
                          </div>
                        </div>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
            <ListPagination
              page={missionsPage.page}
              totalPages={missionsPage.totalPages}
              total={missionsPage.total}
              rangeStart={missionsPage.rangeStart}
              rangeEnd={missionsPage.rangeEnd}
              pageSize={missionsPage.pageSize}
              pageSizeOptions={missionsPage.pageSizeOptions}
              onPageChange={missionsPage.setPage}
              onPageSizeChange={missionsPage.setPageSize}
              label="Mission history pagination"
            />
          </>
        )}
      </div>
    </aside>
  );
}
