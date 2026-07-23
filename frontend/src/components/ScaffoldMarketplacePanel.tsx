import { useEffect, useMemo, useState } from "react";
import { usePagination } from "../hooks/usePagination";
import {
  filterMarketplaceRecipes,
  marketplaceAccessLabel,
  marketplaceEditionBadge,
  recipeCategoryIcon,
  recipeDisplayName,
  scaffoldDisplayName,
  taskCapabilityLabel,
  type MarketplaceRecipe,
} from "../lib/aiLabBranding";
import { ListPagination } from "./ListPagination";

export type MarketplaceState = {
  count?: number;
  can_register?: boolean;
  catalog?: MarketplaceRecipe[];
  categories?: Array<{ id: string; label?: string; count?: number }>;
  registered?: Array<{ id: string; model?: string; base_url?: string }>;
};

type RegisterForm = {
  id: string;
  model: string;
  url: string;
  cost: string;
  message: string | null;
};

type RegisterField = "id" | "model" | "url" | "cost";

type Props = {
  market: MarketplaceState | null;
  disabled?: boolean;
  registerForm: RegisterForm;
  onRegisterField: (field: RegisterField, value: string) => void;
  onRegister: () => void;
  onUnregister: (id: string) => void;
  onRefresh?: () => void;
};

export function ScaffoldMarketplacePanel({
  market,
  disabled = false,
  registerForm,
  onRegisterField,
  onRegister,
  onUnregister,
  onRefresh,
}: Props) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const catalog = market?.catalog ?? [];
  const filtered = useMemo(
    () => filterMarketplaceRecipes(catalog, category, query),
    [catalog, category, query],
  );

  const catalogPage = usePagination(filtered, {
    pageSize: 12,
    pageSizeOptions: [12, 24, 48],
    resetKey: `${category}|${query}`,
  });

  const registered = market?.registered ?? [];
  const registeredPage = usePagination(registered, {
    pageSize: 6,
    pageSizeOptions: [6, 12, 24],
  });

  useEffect(() => {
    setExpandedId(null);
  }, [category, query, catalogPage.page]);

  const categoryCount = market?.categories?.length ?? 0;
  const registeredCount = registered.length;

  return (
    <div className="marketplace-panel" aria-label="Specialist exchange">
      <div className="marketplace-panel__head">
        <div>
          <h3 className="marketplace-panel__title">Specialist Exchange</h3>
          <p className="marketplace-panel__lede">
            Browse cyber specialist recipes and deploy custom inference routes on Pro.
          </p>
        </div>
        {onRefresh && (
          <button type="button" className="btn btn--ghost btn--sm" onClick={onRefresh}>
            Refresh
          </button>
        )}
      </div>

      <div className="marketplace-panel__stats">
        <div className="marketplace-panel__stat">
          <span className="marketplace-panel__stat-value">{catalog.length || "—"}</span>
          <span className="marketplace-panel__stat-label">Specialist recipes</span>
        </div>
        <div className="marketplace-panel__stat">
          <span className="marketplace-panel__stat-value">{categoryCount || "—"}</span>
          <span className="marketplace-panel__stat-label">Mission domains</span>
        </div>
        <div className="marketplace-panel__stat">
          <span className="marketplace-panel__stat-value">{registeredCount}</span>
          <span className="marketplace-panel__stat-label">Deployed routes</span>
        </div>
        <div className="marketplace-panel__stat">
          <span className="marketplace-panel__stat-value">
            {marketplaceEditionBadge(market?.can_register)}
          </span>
          <span className="marketplace-panel__stat-label">
            {marketplaceAccessLabel(market?.can_register)}
          </span>
        </div>
      </div>

      <section className="marketplace-panel__catalog" aria-label="Specialist recipe catalog">
        <div className="marketplace-panel__section-head">
          <div>
            <span className="marketplace-panel__section-label">Recipe catalog</span>
            <span className="marketplace-panel__section-hint">
              OpenAI-compatible specialist models grouped by mission domain
            </span>
          </div>
          <input
            type="search"
            className="marketplace-panel__search"
            placeholder="Search recipes, models, domains…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search specialist recipes"
          />
        </div>

        {market?.categories && market.categories.length > 0 && (
          <div className="marketplace-panel__filters" role="group" aria-label="Filter by domain">
            <button
              type="button"
              className={`marketplace-panel__filter${!category ? " marketplace-panel__filter--active" : ""}`}
              onClick={() => setCategory("")}
            >
              All domains
            </button>
            {market.categories.map((cat) => (
              <button
                key={cat.id}
                type="button"
                className={`marketplace-panel__filter${
                  category === cat.id ? " marketplace-panel__filter--active" : ""
                }`}
                onClick={() => setCategory(cat.id)}
              >
                {cat.label ?? cat.id} ({cat.count ?? 0})
              </button>
            ))}
          </div>
        )}

        <ul className="marketplace-panel__recipe-list">
          {catalogPage.items.map((row) => {
            const expanded = expandedId === row.id;
            return (
              <li
                key={row.id}
                className={`marketplace-panel__recipe${
                  expanded ? " marketplace-panel__recipe--expanded" : ""
                }`}
              >
                <div className="marketplace-panel__recipe-main">
                  <span className="marketplace-panel__recipe-icon" aria-hidden="true">
                    {recipeCategoryIcon(row.category)}
                  </span>
                  <div className="marketplace-panel__recipe-copy">
                    <div className="marketplace-panel__recipe-title">
                      {recipeDisplayName(row)}
                    </div>
                    <div className="marketplace-panel__recipe-sub mono">{row.id}</div>
                    <div className="marketplace-panel__recipe-meta">
                      {row.category && (
                        <span className="marketplace-panel__chip">{row.category}</span>
                      )}
                      {row.model && (
                        <span className="marketplace-panel__chip">
                          {row.model}
                        </span>
                      )}
                      {(row.tasks ?? []).slice(0, 3).map((task) => (
                        <span key={task} className="marketplace-panel__chip marketplace-panel__chip--task">
                          {taskCapabilityLabel(task)}
                        </span>
                      ))}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="marketplace-panel__toggle"
                    aria-expanded={expanded}
                    onClick={() => setExpandedId((current) => (current === row.id ? null : row.id))}
                  >
                    {expanded ? "Hide" : "Details"}
                  </button>
                </div>

                {expanded && (
                  <dl className="marketplace-panel__detail-grid">
                    <div>
                      <dt>Recipe ID</dt>
                      <dd className="mono">{row.id}</dd>
                    </div>
                    <div>
                      <dt>Mission domain</dt>
                      <dd>{row.category ?? "—"}</dd>
                    </div>
                    <div>
                      <dt>Model target</dt>
                      <dd className="mono">{row.model ?? "—"}</dd>
                    </div>
                    <div>
                      <dt>Endpoint hint</dt>
                      <dd className="mono">{row.base_url_hint ?? "—"}</dd>
                    </div>
                    <div>
                      <dt>License</dt>
                      <dd>{row.license ?? "—"}</dd>
                    </div>
                    <div>
                      <dt>Source</dt>
                      <dd>{row.source ?? "builtin"}</dd>
                    </div>
                    <div className="marketplace-panel__detail-wide">
                      <dt>Capabilities</dt>
                      <dd>
                        {(row.tasks ?? []).map(taskCapabilityLabel).join(" · ") || "—"}
                      </dd>
                    </div>
                    {row.notes && (
                      <div className="marketplace-panel__detail-wide">
                        <dt>Operator notes</dt>
                        <dd>{row.notes}</dd>
                      </div>
                    )}
                  </dl>
                )}
              </li>
            );
          })}
          {!catalog.length && (
            <li className="marketplace-panel__empty">No specialist recipes loaded yet.</li>
          )}
          {catalog.length > 0 && filtered.length === 0 && (
            <li className="marketplace-panel__empty">No recipes match this search or filter.</li>
          )}
        </ul>

        <ListPagination
          page={catalogPage.page}
          totalPages={catalogPage.totalPages}
          total={catalogPage.total}
          rangeStart={catalogPage.rangeStart}
          rangeEnd={catalogPage.rangeEnd}
          pageSize={catalogPage.pageSize}
          pageSizeOptions={catalogPage.pageSizeOptions}
          onPageChange={catalogPage.setPage}
          onPageSizeChange={catalogPage.setPageSize}
          label="Specialist recipe pagination"
        />
      </section>

      {registered.length > 0 && (
        <section className="marketplace-panel__deployed" aria-label="Deployed routes">
          <div className="marketplace-panel__section-head">
            <span className="marketplace-panel__section-label">Deployed routes</span>
            <span className="marketplace-panel__section-hint">
              Live specialist endpoints registered in your workspace
            </span>
          </div>
          <ul className="marketplace-panel__route-list">
            {registeredPage.items.map((row) => (
              <li key={row.id} className="marketplace-panel__route">
                <div>
                  <div className="marketplace-panel__route-title">
                    {scaffoldDisplayName(row.id)}
                  </div>
                  <div className="marketplace-panel__route-sub mono">
                    {row.id}
                    {row.model ? ` · ${row.model}` : ""}
                    {row.base_url ? ` · ${row.base_url}` : ""}
                  </div>
                </div>
                {market?.can_register && !disabled && (
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm"
                    onClick={() => onUnregister(row.id)}
                  >
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
          <ListPagination
            page={registeredPage.page}
            totalPages={registeredPage.totalPages}
            total={registeredPage.total}
            rangeStart={registeredPage.rangeStart}
            rangeEnd={registeredPage.rangeEnd}
            pageSize={registeredPage.pageSize}
            pageSizeOptions={registeredPage.pageSizeOptions}
            onPageChange={registeredPage.setPage}
            onPageSizeChange={registeredPage.setPageSize}
            label="Deployed routes pagination"
          />
        </section>
      )}

      {market?.can_register && !disabled && (
        <section className="marketplace-panel__register" aria-label="Deploy custom route">
          <div className="marketplace-panel__section-head">
            <span className="marketplace-panel__section-label">Deploy custom route</span>
            <span className="marketplace-panel__section-hint">Pro — register an OpenAI-compatible endpoint</span>
          </div>
          <div className="marketplace-panel__register-grid">
            <div className="field">
              <label htmlFor="reg-id">Route name</label>
              <input
                id="reg-id"
                value={registerForm.id}
                onChange={(e) => onRegisterField("id", e.target.value)}
                placeholder="my-vllm"
              />
            </div>
            <div className="field">
              <label htmlFor="reg-model">Model ID</label>
              <input
                id="reg-model"
                value={registerForm.model}
                onChange={(e) => onRegisterField("model", e.target.value)}
                placeholder="qwen2.5:14b"
              />
            </div>
            <div className="field">
              <label htmlFor="reg-url">Base URL</label>
              <input
                id="reg-url"
                value={registerForm.url}
                onChange={(e) => onRegisterField("url", e.target.value)}
                placeholder="http://vllm:8000/v1"
              />
            </div>
            <div className="field">
              <label htmlFor="reg-cost">Cost per 1K tokens</label>
              <input
                id="reg-cost"
                value={registerForm.cost}
                onChange={(e) => onRegisterField("cost", e.target.value)}
                placeholder="0"
              />
            </div>
          </div>
          <button
            type="button"
            className="btn btn--primary"
            disabled={!registerForm.id.trim() || !registerForm.model.trim() || !registerForm.url.trim()}
            onClick={onRegister}
          >
            Deploy route
          </button>
          {registerForm.message && <p className="marketplace-panel__message">{registerForm.message}</p>}
        </section>
      )}
    </div>
  );
}
