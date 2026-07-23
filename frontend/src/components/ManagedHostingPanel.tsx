import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  HeartbeatResult,
  PackagingStatus,
  SsoPackagingStatus,
} from "../api/client";
import {
  getEditionHeartbeatPayload,
  sendEditionHeartbeat,
} from "../api/client";
import {
  agentPulseSummary,
  cloudLinkStatusLabel,
  editionDisplayName,
  formatHeartbeatPayload,
  hostingFeatureRows,
  hostingSetupSteps,
  ssoDisplayLabel,
} from "../lib/aiLabBranding";
import { useAuth } from "../providers/AuthProvider";

type Props = {
  packaging: PackagingStatus | null;
  loading?: boolean;
  onRefresh?: () => void;
};

type AdvancedSection = "connect" | "sso" | "pulse";

export function ManagedHostingPanel({ packaging, loading = false, onRefresh }: Props) {
  const { can } = useAuth();
  const isAdmin = can("admin");
  const hosting = packaging?.managed_hosting;
  const sso = packaging?.sso;
  const features = useMemo(() => hostingFeatureRows(packaging?.features), [packaging?.features]);
  const setupSteps = useMemo(
    () => hostingSetupSteps(packaging?.edition, hosting),
    [packaging?.edition, hosting],
  );
  const requiredSteps = setupSteps.filter((step) => step.required);
  const doneRequired = requiredSteps.filter((step) => step.satisfied).length;
  const setupComplete = requiredSteps.every((step) => step.satisfied);
  const enabledFeatures = features.filter((row) => row.enabled);

  const [pulsePreview, setPulsePreview] = useState<Record<string, unknown> | null>(null);
  const [pulseResult, setPulseResult] = useState<HeartbeatResult | null>(null);
  const [pulseBusy, setPulseBusy] = useState(false);
  const [pulseError, setPulseError] = useState<string | null>(null);
  const [expandedSection, setExpandedSection] = useState<AdvancedSection | null>(null);
  const [copied, setCopied] = useState(false);

  const loadPulsePreview = useCallback(async () => {
    if (!isAdmin) return;
    setPulseError(null);
    try {
      const data = await getEditionHeartbeatPayload();
      setPulsePreview(data.payload ?? null);
    } catch (err) {
      setPulseError(err instanceof Error ? err.message : String(err));
    }
  }, [isAdmin]);

  useEffect(() => {
    if (isAdmin) void loadPulsePreview();
  }, [isAdmin, loadPulsePreview, packaging]);

  async function sendPulse() {
    if (!isAdmin) return;
    setPulseBusy(true);
    setPulseError(null);
    try {
      const result = await sendEditionHeartbeat();
      setPulseResult(result);
      setPulsePreview(result.payload ?? pulsePreview);
      setExpandedSection("pulse");
    } catch (err) {
      setPulseError(err instanceof Error ? err.message : String(err));
    } finally {
      setPulseBusy(false);
    }
  }

  async function copyPulsePayload() {
    const text = formatHeartbeatPayload(pulsePreview ?? undefined);
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard unavailable */
    }
  }

  function toggleSection(section: AdvancedSection) {
    setExpandedSection((current) => (current === section ? null : section));
  }

  const cloudStatus = cloudLinkStatusLabel(hosting?.enabled, hosting?.control_plane_url);
  const cloudTone = hosting?.enabled && hosting?.control_plane_url
    ? "ready"
    : hosting?.enabled
      ? "pending"
      : "standby";

  return (
    <div className="hosting-panel" aria-label="Cloud control plane">
      <div className="hosting-panel__toolbar">
        <div className="hosting-panel__summary">
          <span className={`hosting-panel__badge hosting-panel__badge--${cloudTone}`}>
            {cloudStatus}
          </span>
          <span className="hosting-panel__summary-text">
            {editionDisplayName(packaging?.edition)} ·{" "}
            {setupComplete
              ? "Control plane ready"
              : `${doneRequired}/${requiredSteps.length} activation steps complete`}
          </span>
        </div>
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => onRefresh?.()}>
          Refresh
        </button>
      </div>

      {loading && !packaging && (
        <p className="hosting-panel__message">Loading cloud control configuration…</p>
      )}

      <div className="hosting-panel__stats">
        <div className="hosting-panel__stat">
          <span className="hosting-panel__stat-value">{cloudStatus}</span>
          <span className="hosting-panel__stat-label">Cloud link</span>
        </div>
        <div className="hosting-panel__stat">
          <span className="hosting-panel__stat-value">
            {editionDisplayName(packaging?.edition)}
          </span>
          <span className="hosting-panel__stat-label">Edition</span>
        </div>
        <div className="hosting-panel__stat">
          <span className="hosting-panel__stat-value">
            {setupComplete ? "Ready" : `${doneRequired}/${requiredSteps.length}`}
          </span>
          <span className="hosting-panel__stat-label">Activation</span>
        </div>
      </div>

      {features.length > 0 && (
        <div className="hosting-panel__chips" aria-label="Pro modules">
          {features.map((row) => (
            <span
              key={row.key}
              className={`hosting-panel__chip${row.enabled ? " hosting-panel__chip--on" : ""}`}
              title={row.description}
            >
              {row.label}
            </span>
          ))}
          <span className="hosting-panel__chip-meta">
            {enabledFeatures.length}/{features.length} enabled
          </span>
        </div>
      )}

      <div className="hosting-panel__layout">
        <section className="hosting-panel__card" aria-label="Activation checklist">
          <div className="hosting-panel__card-head">
            <span className="hosting-panel__section-label">Get started</span>
            <span className="hosting-panel__section-hint">
              {setupComplete
                ? "Required settings are in place. Use advanced tools below when needed."
                : "Set these environment variables to link this agent to your control plane."}
            </span>
          </div>
          <ul className="hosting-panel__checklist">
            {setupSteps.map((step) => (
              <li
                key={step.env}
                className={`hosting-panel__check${step.satisfied ? " hosting-panel__check--done" : ""}`}
              >
                <span className="hosting-panel__check-mark" aria-hidden="true">
                  {step.satisfied ? "✓" : "○"}
                </span>
                <div>
                  <code className="hosting-panel__check-env">{step.env}</code>
                  <p className="hosting-panel__check-desc">{step.description}</p>
                </div>
              </li>
            ))}
          </ul>
          {packaging?.notes && <p className="hosting-panel__message">{packaging.notes}</p>}
        </section>

        <section className="hosting-panel__card" aria-label="Advanced configuration">
          <div className="hosting-panel__card-head">
            <span className="hosting-panel__section-label">Advanced</span>
            <span className="hosting-panel__section-hint">
              Connection endpoints, enterprise sign-in, and agent pulse
            </span>
          </div>

          <div className="hosting-panel__accordion">
            <HostingAccordion
              id="connect"
              title="Connection profile"
              summary={
                hosting?.control_plane_url
                  ? truncateUrl(hosting.control_plane_url)
                  : "Control plane URL not configured"
              }
              expanded={expandedSection === "connect"}
              onToggle={() => toggleSection("connect")}
            >
              <dl className="hosting-panel__detail-grid">
                <HostingDetail label="Cloud link" value={hosting?.enabled ? "Active" : "Standby"} />
                <HostingDetail label="Console URL" value={hosting?.app_base_url ?? "—"} mono />
                <HostingDetail
                  label="Control plane"
                  value={hosting?.control_plane_url ?? "—"}
                  mono
                />
                <HostingDetail
                  label="Health callback"
                  value={hosting?.health_callback_path ?? "—"}
                  mono
                />
                <HostingDetail label="Tenant header" value={hosting?.tenant_header ?? "—"} mono />
                <HostingDetail
                  label="Pulse endpoint"
                  value={
                    hosting?.control_plane_url
                      ? `${hosting.control_plane_url.replace(/\/$/, "")}/api/v1/agents/heartbeat`
                      : "—"
                  }
                  mono
                />
              </dl>
            </HostingAccordion>

            <HostingAccordion
              id="sso"
              title="Enterprise sign-in"
              summary={ssoDisplayLabel(sso?.ready, sso?.preferred)}
              expanded={expandedSection === "sso"}
              onToggle={() => toggleSection("sso")}
            >
              <SsoDetailGrid sso={sso} />
            </HostingAccordion>

            <HostingAccordion
              id="pulse"
              title="Agent pulse"
              summary={
                pulseResult
                  ? agentPulseSummary(pulseResult)
                  : hosting?.enabled
                    ? "Send a live heartbeat to your control plane"
                    : "Enable managed hosting to send pulses"
              }
              expanded={expandedSection === "pulse"}
              onToggle={() => toggleSection("pulse")}
            >
              {!isAdmin && (
                <p className="hosting-panel__message">
                  Admin role required to preview payloads and send agent pulses.
                </p>
              )}

              <div className="hosting-panel__actions">
                <button
                  type="button"
                  className="btn btn--primary btn--sm"
                  disabled={!isAdmin || pulseBusy || !hosting?.enabled}
                  onClick={() => void sendPulse()}
                >
                  {pulseBusy ? "Sending…" : "Send agent pulse"}
                </button>
              </div>

              {pulseResult && (
                <div
                  className={`hosting-panel__pulse-result${
                    pulseResult.ok ? " hosting-panel__pulse-result--ok" : ""
                  }`}
                >
                  {agentPulseSummary(pulseResult)}
                </div>
              )}

              {pulseError && <p className="error-text">{pulseError}</p>}

              {pulsePreview && (
                <div className="hosting-panel__payload">
                  <div className="hosting-panel__payload-head">
                    <span>Payload preview</span>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      disabled={!isAdmin}
                      onClick={() => void copyPulsePayload()}
                    >
                      {copied ? "Copied" : "Copy JSON"}
                    </button>
                  </div>
                  <pre className="hosting-panel__payload-body">
                    {formatHeartbeatPayload(pulsePreview) ?? "{}"}
                  </pre>
                </div>
              )}
            </HostingAccordion>
          </div>
        </section>
      </div>
    </div>
  );
}

function truncateUrl(value: string, max = 42): string {
  const trimmed = value.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1)}…`;
}

function HostingAccordion({
  id,
  title,
  summary,
  expanded,
  onToggle,
  children,
}: {
  id: string;
  title: string;
  summary: string;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`hosting-panel__accordion-item${
        expanded ? " hosting-panel__accordion-item--expanded" : ""
      }`}
    >
      <button
        type="button"
        className="hosting-panel__accordion-trigger"
        aria-expanded={expanded}
        aria-controls={`hosting-${id}`}
        onClick={onToggle}
      >
        <span className="hosting-panel__accordion-copy">
          <span className="hosting-panel__accordion-title">{title}</span>
          <span className="hosting-panel__accordion-summary">{summary}</span>
        </span>
        <span className="hosting-panel__accordion-chevron" aria-hidden="true">
          {expanded ? "−" : "+"}
        </span>
      </button>
      {expanded && (
        <div className="hosting-panel__accordion-body" id={`hosting-${id}`}>
          {children}
        </div>
      )}
    </div>
  );
}

function HostingDetail({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={mono ? "mono" : undefined}>{value}</dd>
    </div>
  );
}

function SsoDetailGrid({ sso }: { sso?: SsoPackagingStatus }) {
  return (
    <dl className="hosting-panel__detail-grid">
      <HostingDetail label="Ready" value={sso?.ready ? "Yes" : "No"} />
      <HostingDetail label="Preferred provider" value={sso?.preferred ?? "—"} />
      <HostingDetail label="Auth0 configured" value={sso?.auth0?.configured ? "Yes" : "No"} />
      <HostingDetail label="Auth0 domain" value={sso?.auth0?.domain_set ? "Set" : "Missing"} />
      <HostingDetail
        label="Auth0 client ID"
        value={sso?.auth0?.client_id_set ? "Set" : "Missing"}
      />
      <HostingDetail label="OIDC configured" value={sso?.oidc?.configured ? "Yes" : "No"} />
      <HostingDetail label="OIDC issuer" value={sso?.oidc?.issuer ?? "—"} mono />
      {!!sso?.auth0?.missing?.length && (
        <div className="hosting-panel__detail-wide">
          <dt>Missing Auth0 env</dt>
          <dd className="mono">{sso.auth0.missing.join(", ")}</dd>
        </div>
      )}
      {sso?.auth0?.callback_url && (
        <HostingDetail label="Auth0 callback" value={sso.auth0.callback_url} mono />
      )}
    </dl>
  );
}
