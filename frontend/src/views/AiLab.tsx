import { AiLabPanel } from "../components/AiLabPanel";
import { PageHero } from "../components/PageHero";
import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { getAiLabStatus, getScaffolds } from "../api/client";
import {
  AI_LAB_SECTIONS,
  aiLabSectionById,
  isAiLabSectionId,
  type AiLabSectionId,
} from "../lib/aiLabSections";
import { computeTimelineProgress } from "../lib/missionSummary";

type HealthRow = { id: string; ok?: boolean };

export function AiLab() {
  const { section } = useParams<{ section?: string }>();
  const [model, setModel] = useState<string | null>(null);
  const [multiScaffold, setMultiScaffold] = useState(false);
  const [healthy, setHealthy] = useState(0);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getAiLabStatus(), getScaffolds()])
      .then(([status, scaffolds]) => {
        if (cancelled) return;
        const st = status as { model?: string; multi_scaffold?: boolean };
        setModel(st.model ?? null);
        setMultiScaffold(Boolean(st.multi_scaffold));
        const rows = (scaffolds.health as HealthRow[]) ?? [];
        const okCount = rows.filter((row) => row.ok).length;
        setHealthy(okCount);
        setTotal(rows.length);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const progress = useMemo(
    () => computeTimelineProgress(healthy, total),
    [healthy, total],
  );
  const healthTone =
    total === 0 ? "pending" : healthy === total ? "success" : healthy > 0 ? "running" : "failure";

  if (section && !isAiLabSectionId(section)) {
    return <Navigate to="/ai-lab" replace />;
  }

  const activeSection: AiLabSectionId | null = isAiLabSectionId(section) ? section : null;
  const sectionMeta = activeSection ? aiLabSectionById(activeSection) : null;

  return (
    <div className="page-workspace">
      <PageHero
        crumbs={[
          { label: "Console", to: "/missions" },
          { label: "AI Lab", to: "/ai-lab" },
          ...(sectionMeta ? [{ label: sectionMeta.label }] : []),
        ]}
        title={sectionMeta?.label ?? "AI Lab"}
        lede={
          sectionMeta?.description ??
          "Unified workspace for scaffold routing, cyber model marketplace, hosting, and training data."
        }
        status={{
          label:
            total === 0 ? "Loading" : healthy === total ? "All healthy" : "Degraded",
          tone: healthTone,
          pulse: total > 0 && healthy > 0 && healthy < total,
        }}
        badges={
          <>
            {model && <span className="badge badge--ok">{model}</span>}
            {multiScaffold && <span className="badge">Consensus Routing</span>}
          </>
        }
        meta={
          total > 0 ? (
            <span>
              {healthy}/{total} scaffolds healthy · {progress}%
            </span>
          ) : (
            <span>Checking scaffold health…</span>
          )
        }
        progress={total > 0 ? progress : null}
        progressAriaLabel={`Scaffold health ${progress} percent`}
        actions={
          <Link to="/missions" className="btn btn--ghost btn--sm">
            Operations
          </Link>
        }
        error={error}
      />

      <div className="admin-workspace">
        <div className="admin-workspace__main">
          {!activeSection && (
            <AiLabOverview
              model={model}
              multiScaffold={multiScaffold}
              healthy={healthy}
              total={total}
              progress={progress}
            />
          )}

          {activeSection && <AiLabPanel section={activeSection} />}
        </div>
      </div>
    </div>
  );
}

function AiLabOverview({
  model,
  multiScaffold,
  healthy,
  total,
  progress,
}: {
  model: string | null;
  multiScaffold: boolean;
  healthy: number;
  total: number;
  progress: number;
}) {
  return (
    <section className="panel admin-panel" aria-label="AI Lab overview">
      <div className="admin-section-head">
        <div>
          <h2 className="admin-section-head__title">AI Lab hub</h2>
          <p className="admin-section-head__lede">
            Route missions through specialized scaffolds, register models, and grow the training corpus.
          </p>
        </div>
      </div>

      <div className="admin-overview ai-lab-overview-stats">
        <div className="ai-lab-stat-card">
          <span className="ai-lab-stat-card__label">Primary model</span>
          <span className="ai-lab-stat-card__value">{model ?? "—"}</span>
        </div>
        <div className="ai-lab-stat-card">
          <span className="ai-lab-stat-card__label">Scaffold health</span>
          <span className="ai-lab-stat-card__value">
            {total > 0 ? `${healthy}/${total} · ${progress}%` : "Checking…"}
          </span>
        </div>
        <div className="ai-lab-stat-card">
          <span className="ai-lab-stat-card__label">Routing mode</span>
          <span className="ai-lab-stat-card__value">
            {multiScaffold ? "Consensus Routing" : "Single Route"}
          </span>
        </div>
      </div>

      <div className="admin-overview">
        {AI_LAB_SECTIONS.map((section) => (
          <Link key={section.id} to={section.path} className="admin-overview-card">
            <div className="admin-overview-card__head">
              <span className="admin-overview-card__icon" aria-hidden="true">
                {section.icon}
              </span>
              <div>
                <div className="admin-overview-card__title">{section.label}</div>
                <div className="admin-overview-card__group">{section.group}</div>
              </div>
            </div>
            <p className="admin-overview-card__desc">{section.description}</p>
            <span className="admin-overview-card__cta">Open workspace →</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
