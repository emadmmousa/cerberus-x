import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  NAV_GROUPS_KEY,
  SHELL_COLLAPSED_KEY,
  applySidebarCollapsed,
  persistNavGroupExpanded,
  persistSidebarCollapsed,
  readNavGroupExpanded,
  readStoredSidebarCollapsed,
  resolveInitialSidebarCollapsed,
  resolveNavGroupExpanded,
} from "../lib/shellLayout";

function resetShellStorage() {
  try {
    window.localStorage.removeItem(SHELL_COLLAPSED_KEY);
    window.localStorage.removeItem(NAV_GROUPS_KEY);
  } catch {
    /* ignore */
  }
  document.documentElement.removeAttribute("data-sidebar-collapsed");
}

describe("shellLayout helpers", () => {
  beforeEach(() => {
    resetShellStorage();
  });

  afterEach(() => {
    resetShellStorage();
  });

  it("defaults to expanded sidebar", () => {
    expect(readStoredSidebarCollapsed()).toBe(false);
    expect(resolveInitialSidebarCollapsed()).toBe(false);
  });

  it("persists collapsed preference", () => {
    persistSidebarCollapsed(true);
    expect(readStoredSidebarCollapsed()).toBe(true);
    expect(window.localStorage.getItem(SHELL_COLLAPSED_KEY)).toBe("1");
  });

  it("applySidebarCollapsed sets html attribute", () => {
    applySidebarCollapsed(true);
    expect(document.documentElement.hasAttribute("data-sidebar-collapsed")).toBe(true);
    applySidebarCollapsed(false);
    expect(document.documentElement.hasAttribute("data-sidebar-collapsed")).toBe(false);
  });

  it("persists nav group expand state", () => {
    persistNavGroupExpanded("ai-lab", false);
    expect(readNavGroupExpanded("ai-lab")).toBe(false);
    expect(resolveNavGroupExpanded("settings", "/missions")).toBe(true);
  });
});
