import { useEffect, useMemo, useState } from "react";
import type { AuditEvent } from "../api/client";
import { usePagination } from "../hooks/usePagination";
import {
  auditCategoryLabel,
  auditStats,
  filterAuditEvents,
  type AuditCategory,
} from "../lib/auditEvents";
import { AuditEventCard } from "./AuditEventCard";
import { ListPagination } from "./ListPagination";

type Props = {
  events: AuditEvent[];
  error?: string | null;
  onRefresh?: () => void;
  loading?: boolean;
};

const FILTERS: AuditCategory[] = ["all", "training", "missions", "security", "admin"];

export function AuditTimeline({ events, error, onRefresh, loading = false }: Props) {
  const [category, setCategory] = useState<AuditCategory>("all");
  const [query, setQuery] = useState("");
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  const stats = useMemo(() => auditStats(events), [events]);
  const shown = useMemo(
    () => filterAuditEvents(events, category, query),
    [events, category, query],
  );
  const auditPage = usePagination(shown, {
    pageSize: 12,
    pageSizeOptions: [12, 24, 48],
    resetKey: `${category}|${query}`,
  });

  useEffect(() => {
    setExpandedKey(null);
  }, [category, query, auditPage.page]);

  return (
    <section className="panel admin-panel audit-timeline" aria-label="Audit trail">
      <div className="admin-section-head">
        <div>
          <h2 className="admin-section-head__title">Audit trail</h2>
          <p className="admin-section-head__lede">
            Human-readable activity across missions, training data, Access Guard, and admin
            actions.
          </p>
        </div>
        {onRefresh && (
          <button type="button" className="btn btn--ghost btn--sm" onClick={onRefresh}>
            Refresh
          </button>
        )}
      </div>

      <div className="audit-stats">
        <div className="audit-stat">
          <span className="audit-stat__value">{stats.total}</span>
          <span className="audit-stat__label">Recent events</span>
        </div>
        <div className="audit-stat">
          <span className="audit-stat__value">{stats.training}</span>
          <span className="audit-stat__label">Training</span>
        </div>
        <div className="audit-stat">
          <span className="audit-stat__value">{stats.missions}</span>
          <span className="audit-stat__label">Missions</span>
        </div>
        <div className="audit-stat">
          <span className="audit-stat__value">{stats.alerts}</span>
          <span className="audit-stat__label">Alerts</span>
        </div>
      </div>

      <div className="audit-toolbar">
        <div className="audit-filters" role="group" aria-label="Filter audit by category">
          {FILTERS.map((filter) => (
            <button
              key={filter}
              type="button"
              className={`audit-filter${category === filter ? " audit-filter--active" : ""}`}
              onClick={() => setCategory(filter)}
            >
              {filter === "all" ? "All" : auditCategoryLabel(filter)}
            </button>
          ))}
        </div>
        <input
          type="search"
          className="audit-search"
          placeholder="Search events, actors, targets…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search audit trail"
        />
      </div>

      {error && <p className="error-text">{error}</p>}

      <ul className="audit-feed">
        {auditPage.items.map((event, index) => {
          const eventKey = `${event.timestamp ?? "t"}-${event.event_type ?? "e"}-${index}`;
          return (
            <AuditEventCard
              key={eventKey}
              event={event}
              eventKey={eventKey}
              expanded={expandedKey === eventKey}
              onToggle={(key) =>
                setExpandedKey((current) => (current === key ? null : key))
              }
            />
          );
        })}
      </ul>

      <ListPagination
        page={auditPage.page}
        totalPages={auditPage.totalPages}
        total={auditPage.total}
        rangeStart={auditPage.rangeStart}
        rangeEnd={auditPage.rangeEnd}
        pageSize={auditPage.pageSize}
        pageSizeOptions={auditPage.pageSizeOptions}
        onPageChange={auditPage.setPage}
        onPageSizeChange={auditPage.setPageSize}
        label="Audit trail pagination"
      />

      {!loading && shown.length === 0 && !error && (
        <p className="result-card__meta audit-empty">
          No audit events match this view yet — activity will appear here as you work.
        </p>
      )}
    </section>
  );
}
