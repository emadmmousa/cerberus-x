/** Firebreak commercial name for role-based access control (RBAC). */
export const ACCESS_GUARD_PRODUCT = "Access Guard";

export function accessGuardBadge(enforced: boolean): string {
  return enforced ? "Enforced" : "Observe";
}

export function accessGuardOverview(enforced: boolean): string {
  return enforced ? "enforced" : "observe-only";
}
