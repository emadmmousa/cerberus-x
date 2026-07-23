export const SHELL_COLLAPSED_KEY = "firebreak-sidebar-collapsed";
export const NAV_GROUPS_KEY = "firebreak-nav-groups";

export type NavGroupId = "ai-lab" | "settings";

export function readNavGroupExpanded(id: NavGroupId): boolean | null {
  try {
    const storage = globalThis.localStorage;
    if (!storage || typeof storage.getItem !== "function") return null;
    const raw = storage.getItem(NAV_GROUPS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Record<NavGroupId, boolean>>;
    if (typeof parsed[id] === "boolean") return parsed[id]!;
    return null;
  } catch {
    return null;
  }
}

export function persistNavGroupExpanded(id: NavGroupId, expanded: boolean): void {
  try {
    const storage = globalThis.localStorage;
    if (!storage || typeof storage.setItem !== "function") return;
    let parsed: Partial<Record<NavGroupId, boolean>> = {};
    const raw = storage.getItem(NAV_GROUPS_KEY);
    if (raw) {
      parsed = (JSON.parse(raw) as Partial<Record<NavGroupId, boolean>>) ?? {};
    }
    parsed[id] = expanded;
    storage.setItem(NAV_GROUPS_KEY, JSON.stringify(parsed));
  } catch {
    /* ignore */
  }
}

export function resolveNavGroupExpanded(id: NavGroupId, pathname: string): boolean {
  const stored = readNavGroupExpanded(id);
  if (stored !== null) return stored;
  const prefix = id === "ai-lab" ? "/ai-lab" : "/admin";
  return pathname.startsWith(prefix) || true;
}

export function readStoredSidebarCollapsed(): boolean {
  try {
    const storage = globalThis.localStorage;
    if (!storage || typeof storage.getItem !== "function") return false;
    return storage.getItem(SHELL_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

export function resolveInitialSidebarCollapsed(): boolean {
  return readStoredSidebarCollapsed();
}

export function applySidebarCollapsed(collapsed: boolean): void {
  if (typeof document === "undefined") return;
  document.documentElement.toggleAttribute("data-sidebar-collapsed", collapsed);
}

export function persistSidebarCollapsed(collapsed: boolean): void {
  try {
    const storage = globalThis.localStorage;
    if (!storage || typeof storage.setItem !== "function") return;
    storage.setItem(SHELL_COLLAPSED_KEY, collapsed ? "1" : "0");
  } catch {
    /* ignore */
  }
}
