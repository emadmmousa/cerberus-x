import { type CSSProperties, type ReactNode } from "react";
import { Link } from "react-router-dom";

export type PageHeroStatusTone =
  | "running"
  | "success"
  | "failure"
  | "pending"
  | "neutral";

type Crumb = { label: string; to?: string };

type Props = {
  crumbs: Crumb[];
  title: string;
  lede?: string;
  status?: { label: string; tone: PageHeroStatusTone; pulse?: boolean };
  badges?: ReactNode;
  meta?: ReactNode;
  progress?: number | null;
  progressAriaLabel?: string;
  actions?: ReactNode;
  error?: string | null;
};

export function PageHero({
  crumbs,
  title,
  lede,
  status,
  badges,
  meta,
  progress,
  progressAriaLabel,
  actions,
  error,
}: Props) {
  const progressValue =
    progress == null ? null : Math.min(100, Math.max(0, Math.round(progress)));

  return (
    <header className="page-hero panel">
      <nav className="page-hero__crumb" aria-label="Breadcrumb">
        {crumbs.map((crumb, index) => (
          <span key={`${crumb.label}-${index}`} className="page-hero__crumb-item">
            {index > 0 && <span aria-hidden="true">/</span>}
            {crumb.to ? <Link to={crumb.to}>{crumb.label}</Link> : <span>{crumb.label}</span>}
          </span>
        ))}
      </nav>

      <div className="page-hero__main">
        <div className="page-hero__copy">
          {(status || badges) && (
            <div className="page-hero__badges">
              {status && (
                <span className={`page-hero__status page-hero__status--${status.tone}`}>
                  {status.pulse && status.tone === "running" && (
                    <span className="page-hero__pulse" aria-hidden="true" />
                  )}
                  {status.label}
                </span>
              )}
              {badges}
            </div>
          )}
          <h1 className="page-hero__title">{title}</h1>
          {lede && <p className="page-hero__lede">{lede}</p>}
          {meta && <div className="page-hero__meta">{meta}</div>}
        </div>

        {(progressValue != null || actions) && (
          <div className="page-hero__aside">
            {progressValue != null && (
              <div
                className="page-hero__ring"
                style={
                  { "--page-progress": `${progressValue}%` } as CSSProperties
                }
                role="img"
                aria-label={progressAriaLabel ?? `Progress ${progressValue} percent`}
              >
                <span className="page-hero__ring-value">{progressValue}%</span>
              </div>
            )}
            {actions}
          </div>
        )}
      </div>

      {error && <p className="error-text page-hero__error">{error}</p>}
    </header>
  );
}
