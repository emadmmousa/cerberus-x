import type { AuditEvent } from "../api/client";

export type AuditCategory = "all" | "training" | "missions" | "security" | "admin";

export type AuditCategoryFilter = Exclude<AuditCategory, "all">;

const EVENT_LABELS: Record<string, string> = {
  DATASET_CONTRIBUTE: "Training example contributed",
  AI_SCAFFOLD_DISAGREEMENT: "Scaffold consensus disagreement",
  AI_MISSION_COMPLETE: "AI mission completed",
  AI_MISSION_FAILED: "AI mission failed",
  PLAYBOOK_SUBMITTED: "Mission launched",
  PLAYBOOK_FAILED: "Mission launch failed",
  MISSION_STOP: "Mission stopped",
  MISSION_RESTART: "Mission restarted",
  MISSION_DELETE: "Mission deleted",
  MISSION_EDIT: "Mission updated",
  LOGIN_SUCCESS: "Sign-in successful",
  SIGNUP_SUCCESS: "Account created",
  OIDC_LOGIN: "SSO sign-in",
  OIDC_CALLBACK_FAILED: "SSO callback failed",
  AUTH0_CALLBACK_FAILED: "Auth0 callback failed",
  ADMIN_USER_CREATE: "User created",
  ADMIN_USER_UPDATE: "User updated",
  ADMIN_USER_DELETE: "User deleted",
  ADMIN_RBAC_SET: "Access Guard policy changed",
  ADMIN_EDITION_SET: "Edition changed",
  ADMIN_OPS_SET: "Ops automation changed",
  AUTHZ_TARGET_ADDED: "Authorized target added",
  AUTHZ_TARGET_REMOVED: "Authorized target removed",
  AUTHZ_TARGET_API_ADD: "Target allow-list updated",
  AUTHZ_TARGET_API_REMOVE: "Target removed from allow-list",
  LEARNING_TICK: "Learning harvest completed",
  AUTO_TRAIN_DAILY: "Auto-train job finished",
  VULN_DETECTED: "Vulnerability detected",
  SCAN_STARTED: "Scan started",
  CUSTOM_TOOL_REGISTERED: "Custom tool registered",
  CUSTOM_TOOL_DELETED: "Custom tool removed",
};

const CATEGORY_LABELS: Record<AuditCategoryFilter, string> = {
  training: "Training",
  missions: "Missions",
  security: "Security",
  admin: "Administration",
};

export function auditEventLabel(eventType?: string): string {
  const key = (eventType ?? "").trim();
  if (!key) return "Unknown event";
  if (EVENT_LABELS[key]) return EVENT_LABELS[key];
  return key
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function auditEventCategory(eventType?: string): AuditCategoryFilter {
  const t = (eventType ?? "").toUpperCase();
  if (t.includes("DATASET") || t.includes("LEARNING") || t.includes("AUTO_TRAIN")) {
    return "training";
  }
  if (t.startsWith("ADMIN_")) return "admin";
  if (
    t.includes("LOGIN") ||
    t.includes("SIGNUP") ||
    t.includes("OIDC") ||
    t.includes("AUTH0") ||
    t.includes("AUTHZ") ||
    t.includes("MFA") ||
    t.includes("WAF")
  ) {
    return "security";
  }
  return "missions";
}

export function auditCategoryLabel(category: AuditCategoryFilter): string {
  return CATEGORY_LABELS[category];
}

export function auditEventSummary(event: AuditEvent): string {
  const data =
    event.data && typeof event.data === "object"
      ? (event.data as Record<string, unknown>)
      : {};
  const type = (event.event_type ?? "").toUpperCase();

  if (type === "DATASET_CONTRIBUTE") {
    const posture = data.posture ?? "balanced";
    const id = data.id ?? data.record_id;
    return id ? `Posture ${posture} · saved as ${id}` : `Posture ${posture}`;
  }
  if (type.includes("MISSION") || type.includes("PLAYBOOK")) {
    const parts = [
      data.target ? `Target ${data.target}` : null,
      data.job_id ? `Job ${String(data.job_id).slice(0, 8)}…` : null,
    ].filter(Boolean);
    return parts.length ? parts.join(" · ") : "Mission activity recorded";
  }
  if (type === "AI_SCAFFOLD_DISAGREEMENT") {
    const conf = data.confidence;
    return typeof conf === "number"
      ? `Low consensus (${Math.round(conf * 100)}%) across scaffolds`
      : "Planners disagreed on the next step";
  }
  if (type.startsWith("ADMIN_")) {
    return data.enforce != null
      ? `Access Guard ${data.enforce ? "enforced" : "observe-only"}`
      : "Settings change recorded";
  }
  if (type.includes("AUTHZ") || type.includes("TARGET")) {
    return data.target ? `Target ${data.target}` : "Scope change recorded";
  }
  if (type === "LOGIN_SUCCESS" || type === "OIDC_LOGIN") {
    return event.source_ip ? `From ${event.source_ip}` : "Session established";
  }

  const keys = Object.keys(data).slice(0, 3);
  if (keys.length === 0) return "No additional detail";
  return keys.map((k) => `${k}: ${String(data[k]).slice(0, 48)}`).join(" · ");
}

export function auditEventIcon(eventType?: string): string {
  const category = auditEventCategory(eventType);
  if (category === "training") return "📚";
  if (category === "security") return "🔐";
  if (category === "admin") return "⚙";
  if ((eventType ?? "").includes("FAILED") || (eventType ?? "").includes("DISAGREEMENT")) {
    return "⚠";
  }
  return "◎";
}

export function auditSeverityTone(severity?: string): "info" | "warn" | "critical" {
  const s = (severity ?? "info").toLowerCase();
  if (s === "critical" || s === "high") return "critical";
  if (s === "medium" || s === "warning") return "warn";
  return "info";
}

export function formatAuditTime(timestamp?: string): string {
  if (!timestamp) return "Just now";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  const now = Date.now();
  const diffMs = now - date.getTime();
  if (diffMs < 60_000) return "Just now";
  if (diffMs < 3_600_000) return `${Math.floor(diffMs / 60_000)}m ago`;
  if (diffMs < 86_400_000) return `${Math.floor(diffMs / 3_600_000)}h ago`;
  return date.toLocaleString();
}

export function formatAuditTimestampFull(timestamp?: string): string {
  if (!timestamp) return "Unknown time";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  });
}

export type AuditDetailRow = {
  label: string;
  value: string;
  mono?: boolean;
  href?: string;
};

function humanizeKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatAuditValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "—";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    return value.length ? value.map((item) => formatAuditValue(item)).join(", ") : "—";
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function parseAuditData(data: unknown): Record<string, unknown> {
  if (data == null) return {};
  if (typeof data === "object" && !Array.isArray(data)) {
    return data as Record<string, unknown>;
  }
  return { payload: data };
}

function dataDetailRow(key: string, value: unknown): AuditDetailRow {
  const label = humanizeKey(key);
  const formatted = formatAuditValue(value);
  const row: AuditDetailRow = {
    label,
    value: formatted,
    mono:
      key.includes("id") ||
      key.includes("job") ||
      key.includes("target") ||
      key.includes("ip") ||
      key.includes("url"),
  };

  if (key === "job_id" && typeof value === "string" && value.trim()) {
    row.href = `/missions/${value.trim()}`;
  }
  if (key === "target" && typeof value === "string") {
    const target = value.trim();
    if (/^https?:\/\//i.test(target)) row.href = target;
  }
  if (key === "new_id" && typeof value === "string" && value.trim()) {
    row.href = `/missions/${value.trim()}`;
  }

  return row;
}

/** Structured rows for the expanded audit detail panel. */
export function auditEventDetails(event: AuditEvent): AuditDetailRow[] {
  const rows: AuditDetailRow[] = [
    {
      label: "Event code",
      value: event.event_type ?? "UNKNOWN",
      mono: true,
    },
    {
      label: "Recorded at",
      value: formatAuditTimestampFull(event.timestamp),
      mono: true,
    },
    { label: "Actor", value: event.actor ?? "system" },
  ];

  if (event.actor_role) rows.push({ label: "Role", value: event.actor_role });
  if (event.actor_org) rows.push({ label: "Organization", value: event.actor_org, mono: true });
  if (event.source_ip) rows.push({ label: "Source IP", value: event.source_ip, mono: true });

  rows.push(
    { label: "Severity", value: (event.severity ?? "info").toUpperCase() },
    {
      label: "Category",
      value: auditCategoryLabel(auditEventCategory(event.event_type)),
    },
  );

  for (const [key, value] of Object.entries(parseAuditData(event.data))) {
    rows.push(dataDetailRow(key, value));
  }

  return rows;
}

export function formatAuditPayload(data: unknown): string | null {
  if (data == null) return null;
  if (typeof data === "string") return data;
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

export function auditEventSearchBlob(event: AuditEvent): string {
  return [
    event.event_type,
    auditEventLabel(event.event_type),
    auditEventSummary(event),
    event.actor,
    event.actor_role,
    event.actor_org,
    event.severity,
    event.source_ip,
    formatAuditPayload(event.data),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function auditStats(events: AuditEvent[]) {
  let training = 0;
  let missions = 0;
  let security = 0;
  let admin = 0;
  let alerts = 0;

  for (const event of events) {
    const cat = auditEventCategory(event.event_type);
    if (cat === "training") training += 1;
    else if (cat === "security") security += 1;
    else if (cat === "admin") admin += 1;
    else missions += 1;
    if (auditSeverityTone(event.severity) !== "info") alerts += 1;
  }

  return { total: events.length, training, missions, security, admin, alerts };
}

export function filterAuditEvents(
  events: AuditEvent[],
  category: AuditCategory,
  query: string,
): AuditEvent[] {
  const q = query.trim().toLowerCase();
  return events.filter((event) => {
    if (category !== "all" && auditEventCategory(event.event_type) !== category) {
      return false;
    }
    if (!q) return true;
    return auditEventSearchBlob(event).includes(q);
  });
}
