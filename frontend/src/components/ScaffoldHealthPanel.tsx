import { useMemo, useState } from "react";
import { usePagination } from "../hooks/usePagination";
import {
  costPer1kLabel,
  costRoutingLabel,
  editionDisplayName,
  foundationModelLabel,
  healthStatusLabel,
  latencyLabel,
  modelDisplayName,
  platformCapabilities,
  routingModeLabel,
  scaffoldDisplayName,
  scaffoldTechnicalLabel,
  ssoDisplayLabel,
} from "../lib/aiLabBranding";
import { ListPagination } from "./ListPagination";

export type ScaffoldHealthRow = {
  id: string;
  model?: string;
  base_url?: string;
  ok?: boolean;
  latency_ms?: number;
  latency_ema_ms?: number;
  cost_per_1k?: number;
  error?: string;
};

export type ScaffoldRuntimeStatus = {
  model?: string;
  base_model?: string;
  multi_scaffold?: boolean;
  cost_route?: boolean;
  edition?: { edition?: string };
  sso?: { ready?: boolean; preferred?: string | null };
  waves?: Record<string, boolean>;
};

type Props = {
  status: ScaffoldRuntimeStatus | null;
  health: ScaffoldHealthRow[];
  error?: string | null;
  onRefresh?: () => void;
};

export function ScaffoldHealthPanel({ status, health, error, onRefresh }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const capabilities = useMemo(() => platformCapabilities(status?.waves), [status?.waves]);
  const healthyCount = health.filter((row) => row.ok).length;
  const avgLatency = useMemo(() => {
    const samples = health
      .filter((row) => row.ok)
      .map((row) => row.latency_ema_ms ?? row.latency_ms)
      .filter((value): value is number => typeof value === "number" && !Number.isNaN(value));
    if (!samples.length) return null;
    return Math.round(samples.reduce((sum, value) => sum + value, 0) / samples.length);
  }, [health]);

  const endpointsPage = usePagination(health, {
    pageSize: 6,
    pageSizeOptions: [6, 12, 24],
  });

  const runtimeTags = [
    routingModeLabel(status?.multi_scaffold),
    costRoutingLabel(status?.cost_route),
    editionDisplayName(status?.edition?.edition),
    ssoDisplayLabel(status?.sso?.ready, status?.sso?.preferred),
  ].filter(Boolean);

  return (
    <div className="scaffold-health" aria-label="Model router health">
      <div className="scaffold-health__head">
        <div>
          <h3 className="scaffold-health__title">Model Router</h3>
          <p className="scaffold-health__lede">
            Commercial view of inference routes, latency, and enabled platform capabilities.
          </p>
        </div>
        {onRefresh && (
          <button type="button" className="btn btn--ghost btn--sm" onClick={onRefresh}>
            Refresh
          </button>
        )}
      </div>

      <div className="scaffold-health__stats">
        <div className="scaffold-health__stat">
          <span className="scaffold-health__stat-value">
            {health.length ? `${healthyCount}/${health.length}` : "—"}
          </span>
          <span className="scaffold-health__stat-label">Routes online</span>
        </div>
        <div className="scaffold-health__stat">
          <span className="scaffold-health__stat-value">{latencyLabel(avgLatency)}</span>
          <span className="scaffold-health__stat-label">Avg response</span>
        </div>
        <div className="scaffold-health__stat">
          <span className="scaffold-health__stat-value">
            {routingModeLabel(status?.multi_scaffold)}
          </span>
          <span className="scaffold-health__stat-label">Routing mode</span>
        </div>
        <div className="scaffold-health__stat">
          <span className="scaffold-health__stat-value">{capabilities.length}</span>
          <span className="scaffold-health__stat-label">Capabilities live</span>
        </div>
      </div>

      <section className="scaffold-health__profile" aria-label="Runtime profile">
        <div className="scaffold-health__profile-head">
          <span className="scaffold-health__section-label">Runtime profile</span>
        </div>
        <div className="scaffold-health__profile-grid">
          <div className="scaffold-health__profile-item">
            <span className="scaffold-health__profile-label">Deployed model</span>
            <strong className="scaffold-health__profile-value">
              {modelDisplayName(status?.model)}
            </strong>
            <span className="scaffold-health__profile-meta mono">
              {foundationModelLabel(status?.base_model)}
            </span>
          </div>
          <div className="scaffold-health__profile-item">
            <span className="scaffold-health__profile-label">Edition & access</span>
            <div className="scaffold-health__tags">
              {runtimeTags.map((tag) => (
                <span key={tag} className="scaffold-health__tag">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {capabilities.length > 0 && (
        <section className="scaffold-health__capabilities" aria-label="Platform capabilities">
          <div className="scaffold-health__section-head">
            <span className="scaffold-health__section-label">Platform capabilities</span>
            <span className="scaffold-health__section-hint">Commercial modules enabled in this stack</span>
          </div>
          <div className="scaffold-health__cap-grid">
            {capabilities.map((cap) => (
              <article key={cap.id} className="scaffold-health__cap-card">
                <span className="scaffold-health__cap-icon" aria-hidden="true">
                  {cap.icon}
                </span>
                <div>
                  <div className="scaffold-health__cap-title">{cap.label}</div>
                  <p className="scaffold-health__cap-desc">{cap.description}</p>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="scaffold-health__routes" aria-label="Inference routes">
        <div className="scaffold-health__section-head">
          <span className="scaffold-health__section-label">Inference routes</span>
          <span className="scaffold-health__section-hint">Live endpoint health and economics</span>
        </div>

        {error && <p className="error-text">{error}</p>}

        <ul className="scaffold-health__route-list">
          {endpointsPage.items.map((row) => {
            const expanded = expandedId === row.id;
            const latency = row.latency_ema_ms ?? row.latency_ms;
            return (
              <li
                key={row.id}
                className={`scaffold-health__route${row.ok ? "" : " scaffold-health__route--down"}${
                  expanded ? " scaffold-health__route--expanded" : ""
                }`}
              >
                <div className="scaffold-health__route-main">
                  <div className="scaffold-health__route-copy">
                    <div className="scaffold-health__route-title">
                      {scaffoldDisplayName(row.id)}
                    </div>
                    <div className="scaffold-health__route-sub mono">
                      {scaffoldTechnicalLabel(row.id)}
                      {row.model ? ` · ${row.model}` : ""}
                    </div>
                  </div>
                  <div className="scaffold-health__route-metrics">
                    <span
                      className={`scaffold-health__status scaffold-health__status--${
                        row.ok ? "online" : "offline"
                      }`}
                    >
                      {healthStatusLabel(row.ok)}
                    </span>
                    <span className="scaffold-health__metric">{latencyLabel(latency)}</span>
                    <span className="scaffold-health__metric">
                      {costPer1kLabel(row.cost_per_1k)}
                    </span>
                    <button
                      type="button"
                      className="scaffold-health__toggle"
                      aria-expanded={expanded}
                      onClick={() => setExpandedId((current) => (current === row.id ? null : row.id))}
                    >
                      {expanded ? "Hide" : "Details"}
                    </button>
                  </div>
                </div>

                {expanded && (
                  <dl className="scaffold-health__detail-grid">
                    <div>
                      <dt>Endpoint ID</dt>
                      <dd className="mono">{row.id}</dd>
                    </div>
                    <div>
                      <dt>Model</dt>
                      <dd className="mono">{row.model ?? "—"}</dd>
                    </div>
                    <div>
                      <dt>Base URL</dt>
                      <dd className="mono">{row.base_url ?? "—"}</dd>
                    </div>
                    <div>
                      <dt>Last latency</dt>
                      <dd>{latencyLabel(row.latency_ms)}</dd>
                    </div>
                    <div>
                      <dt>Smoothed latency</dt>
                      <dd>{latencyLabel(row.latency_ema_ms)}</dd>
                    </div>
                    <div>
                      <dt>Token cost</dt>
                      <dd>{costPer1kLabel(row.cost_per_1k)}</dd>
                    </div>
                    {!row.ok && row.error && (
                      <div className="scaffold-health__detail-error">
                        <dt>Status note</dt>
                        <dd>{row.error}</dd>
                      </div>
                    )}
                  </dl>
                )}
              </li>
            );
          })}
          {!health.length && !error && (
            <li className="scaffold-health__empty">No inference routes registered yet.</li>
          )}
        </ul>

        <ListPagination
          page={endpointsPage.page}
          totalPages={endpointsPage.totalPages}
          total={endpointsPage.total}
          rangeStart={endpointsPage.rangeStart}
          rangeEnd={endpointsPage.rangeEnd}
          pageSize={endpointsPage.pageSize}
          pageSizeOptions={endpointsPage.pageSizeOptions}
          onPageChange={endpointsPage.setPage}
          onPageSizeChange={endpointsPage.setPageSize}
          label="Inference routes pagination"
        />
      </section>
    </div>
  );
}
