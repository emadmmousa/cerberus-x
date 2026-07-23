import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { AuditEvent } from "../api/client";
import {
  auditCategoryLabel,
  auditEventCategory,
  auditEventDetails,
  auditEventIcon,
  auditEventLabel,
  auditEventSummary,
  auditSeverityTone,
  formatAuditPayload,
  formatAuditTime,
} from "../lib/auditEvents";

type Props = {
  event: AuditEvent;
  eventKey: string;
  expanded?: boolean;
  onToggle?: (eventKey: string) => void;
};

export function AuditEventCard({ event, eventKey, expanded = false, onToggle }: Props) {
  const [copied, setCopied] = useState(false);
  const tone = auditSeverityTone(event.severity);
  const cat = auditEventCategory(event.event_type);
  const details = useMemo(() => auditEventDetails(event), [event]);
  const payload = useMemo(() => formatAuditPayload(event.data), [event.data]);
  const hasPayload = payload != null && payload.trim().length > 0;

  async function copyPayload() {
    if (!payload) return;
    try {
      await navigator.clipboard.writeText(payload);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <li
      className={`audit-card audit-card--${tone}${expanded ? " audit-card--expanded" : ""}`}
    >
      <div className="audit-card__shell">
        <div className="audit-card__icon" aria-hidden="true">
          {auditEventIcon(event.event_type)}
        </div>

        <div className="audit-card__body">
          <div className="audit-card__head">
            <span className="audit-card__title">{auditEventLabel(event.event_type)}</span>
            <time className="audit-card__time" dateTime={event.timestamp}>
              {formatAuditTime(event.timestamp)}
            </time>
          </div>
          <p className="audit-card__summary">{auditEventSummary(event)}</p>
          <div className="audit-card__meta">
            <span className="audit-card__chip">{auditCategoryLabel(cat)}</span>
            <span className="audit-card__chip">
              {event.actor ?? "system"}
              {event.actor_role ? ` · ${event.actor_role}` : ""}
            </span>
            <span className={`audit-card__severity audit-card__severity--${tone}`}>
              {(event.severity ?? "info").toUpperCase()}
            </span>
            <button
              type="button"
              className="audit-card__toggle"
              aria-expanded={expanded}
              aria-controls={`audit-detail-${eventKey}`}
              onClick={() => onToggle?.(eventKey)}
            >
              {expanded ? "Hide details" : "View details"}
            </button>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="audit-card__details" id={`audit-detail-${eventKey}`}>
          <dl className="audit-detail-grid">
            {details.map((row) => (
              <div key={`${eventKey}-${row.label}`} className="audit-detail-grid__row">
                <dt className="audit-detail-grid__label">{row.label}</dt>
                <dd
                  className={`audit-detail-grid__value${
                    row.mono ? " audit-detail-grid__value--mono" : ""
                  }`}
                >
                  {row.href?.startsWith("/") ? (
                    <Link to={row.href} className="audit-detail-grid__link">
                      {row.value}
                    </Link>
                  ) : row.href ? (
                    <a
                      href={row.href}
                      className="audit-detail-grid__link"
                      target="_blank"
                      rel="noreferrer"
                    >
                      {row.value}
                    </a>
                  ) : (
                    row.value
                  )}
                </dd>
              </div>
            ))}
          </dl>

          {hasPayload && (
            <div className="audit-card__payload">
              <div className="audit-card__payload-head">
                <span>Raw event payload</span>
                <button
                  type="button"
                  className="btn btn--ghost btn--sm"
                  onClick={() => void copyPayload()}
                >
                  {copied ? "Copied" : "Copy JSON"}
                </button>
              </div>
              <pre className="audit-card__payload-body">{payload}</pre>
            </div>
          )}
        </div>
      )}
    </li>
  );
}
