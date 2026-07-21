import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import {
  THEME_STORAGE_KEY,
  applyTheme,
  isTheme,
  persistTheme,
  readStoredTheme,
  resolveInitialTheme,
  toggleTheme,
} from "../lib/theme";
import { ThemeProvider } from "../providers/ThemeProvider";
import { ThemeToggle } from "../components/ThemeToggle";
import { AuthProvider } from "../providers/AuthProvider";
import { AppShell } from "../components/AppShell";

function resetThemeStorage() {
  try {
    window.localStorage.removeItem(THEME_STORAGE_KEY);
  } catch {
    /* ignore */
  }
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.style.colorScheme = "";
}

describe("theme helpers", () => {
  beforeEach(() => {
    resetThemeStorage();
  });

  afterEach(() => {
    resetThemeStorage();
    vi.unstubAllGlobals();
  });

  it("validates theme values", () => {
    expect(isTheme("dark")).toBe(true);
    expect(isTheme("light")).toBe(true);
    expect(isTheme("neon")).toBe(false);
  });

  it("toggles dark ↔ light", () => {
    expect(toggleTheme("dark")).toBe("light");
    expect(toggleTheme("light")).toBe("dark");
  });

  it("persists and reads theme", () => {
    persistTheme("light");
    expect(readStoredTheme()).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("applyTheme sets data-theme and color-scheme", () => {
    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
  });

  it("resolveInitialTheme prefers stored over system", () => {
    persistTheme("light");
    expect(resolveInitialTheme()).toBe("light");
  });

  it("resolveInitialTheme falls back to system preference", () => {
    const matchMedia = vi.fn().mockReturnValue({ matches: true });
    vi.stubGlobal("matchMedia", matchMedia);
    expect(resolveInitialTheme()).toBe("light");
  });
});

describe("ThemeToggle", () => {
  beforeEach(() => {
    resetThemeStorage();
    applyTheme("dark");
  });

  afterEach(() => {
    resetThemeStorage();
  });

  it("switches to light and persists", () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    const btn = screen.getByRole("button", { name: /switch to light theme/i });
    fireEvent.click(btn);

    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(
      screen.getByRole("button", { name: /switch to dark theme/i }),
    ).toBeInTheDocument();
  });
});

describe("AppShell theme chrome", () => {
  beforeEach(() => {
    resetThemeStorage();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (
          url === "/api/rbac/me" ||
          url === "/auth/status" ||
          url === "/api/oidc/status"
        ) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              authenticated: false,
              role: "operator",
              org_id: "default",
              rbac_enforce: false,
              configured: false,
            }),
          });
        }
        return Promise.resolve({ ok: true, json: async () => ({}) });
      }),
    );
  });

  afterEach(() => {
    resetThemeStorage();
    vi.unstubAllGlobals();
  });

  it("exposes theme toggle in the nav", () => {
    render(
      <MemoryRouter>
        <ThemeProvider>
          <AuthProvider>
            <AppShell />
          </AuthProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("button", { name: /switch to light theme/i }),
    ).toBeInTheDocument();
  });
});
