import { ACCESS_GUARD_PRODUCT } from "./accessGuard";

export type AdminSectionId =
  | "users"
  | "orgs"
  | "auth"
  | "rbac"
  | "edition"
  | "ops"
  | "targets"
  | "missions"
  | "logs";

export type AdminSectionGroup = "Identity & access" | "Platform" | "Operations";

export type AdminSection = {
  id: AdminSectionId;
  path: `/admin/${AdminSectionId}`;
  label: string;
  icon: string;
  group: AdminSectionGroup;
  description: string;
};

export const ADMIN_SECTIONS: AdminSection[] = [
  {
    id: "users",
    path: "/admin/users",
    label: "Users",
    icon: "👤",
    group: "Identity & access",
    description: "Create accounts, assign roles, and manage credentials.",
  },
  {
    id: "orgs",
    path: "/admin/orgs",
    label: "Organizations",
    icon: "🏢",
    group: "Identity & access",
    description: "Tenants, org membership, and isolation boundaries.",
  },
  {
    id: "auth",
    path: "/admin/auth",
    label: "Authentication",
    icon: "🔑",
    group: "Identity & access",
    description: "Local, OIDC, and Auth0 sign-in methods.",
  },
  {
    id: "rbac",
    path: "/admin/rbac",
    label: ACCESS_GUARD_PRODUCT,
    icon: "🛡",
    group: "Identity & access",
    description: "Who can launch missions — viewer, operator, or admin roles.",
  },
  {
    id: "edition",
    path: "/admin/edition",
    label: "Edition",
    icon: "💎",
    group: "Platform",
    description: "Community vs Pro packaging and feature flags.",
  },
  {
    id: "ops",
    path: "/admin/ops",
    label: "Ops & automation",
    icon: "⚡",
    group: "Platform",
    description: "Auto-scale, training ticks, and runtime automation.",
  },
  {
    id: "targets",
    path: "/admin/targets",
    label: "Authorized targets",
    icon: "🎯",
    group: "Operations",
    description: "Allow-listed hosts and engagement scope.",
  },
  {
    id: "missions",
    path: "/admin/missions",
    label: "Mission control",
    icon: "🛰",
    group: "Operations",
    description: "Stop, restart, and purge mission jobs.",
  },
  {
    id: "logs",
    path: "/admin/logs",
    label: "Audit",
    icon: "📋",
    group: "Operations",
    description: "Human-readable trail of missions, training, and admin actions.",
  },
];

const SECTION_IDS = new Set(ADMIN_SECTIONS.map((s) => s.id));

export function isAdminSectionId(value: string | undefined): value is AdminSectionId {
  return Boolean(value && SECTION_IDS.has(value as AdminSectionId));
}

export function adminSectionById(id: AdminSectionId): AdminSection {
  return ADMIN_SECTIONS.find((s) => s.id === id)!;
}

export function adminSectionsByGroup(): Array<{ group: AdminSectionGroup; sections: AdminSection[] }> {
  const groups: AdminSectionGroup[] = ["Identity & access", "Platform", "Operations"];
  return groups.map((group) => ({
    group,
    sections: ADMIN_SECTIONS.filter((s) => s.group === group),
  }));
}

export function adminPageTitle(section?: string): string {
  if (isAdminSectionId(section)) {
    return adminSectionById(section).label;
  }
  return "Administration";
}
