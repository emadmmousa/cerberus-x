import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../providers/AuthProvider";
import { ThemeProvider } from "../providers/ThemeProvider";
import { Admin } from "../views/Admin";

vi.mock("../api/socket", () => ({
  getSocket: () => ({ on: vi.fn(), off: vi.fn() }),
  disconnectSocket: vi.fn(),
}));

const mockSettings = {
  settings: {
    rbac_enforce: null,
    edition: null,
    auth_methods: { local: true },
    auto_scale: null,
    auto_train: null,
    learning_tick: null,
  },
  effective: {
    rbac_enforce: false,
    edition: "community",
    auto_scale: false,
    auto_train: false,
    learning_tick: false,
  },
  options: {
    editions: ["community", "pro"],
    roles: ["viewer", "operator", "admin"],
    auth_methods: ["local", "auth0"],
  },
  sso: { ready: false },
  secret_key_insecure: true,
};

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>(
    "../api/client",
  );
  return {
    ...actual,
    listAdminUsers: vi.fn(async () => []),
    listAdminOrgs: vi.fn(async () => [{ id: "default", name: "Default", user_count: 0 }]),
    listMissions: vi.fn(async () => ({ missions: [], count: 0 })),
    getAdminSettings: vi.fn(async () => mockSettings),
    setOpsSettings: vi.fn(async (body) => ({
      ...mockSettings.settings,
      ...body,
    })),
  };
});

import { getAdminSettings, setOpsSettings } from "../api/client";

function renderAdmin() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url === "/api/rbac/me") {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            authenticated: true,
            user: "admin",
            role: "admin",
            org_id: "default",
            rbac_enforce: false,
          }),
        });
      }
      if (url === "/auth/status") {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            authenticated: true,
            user: "admin",
            role: "admin",
          }),
        });
      }
      if (url === "/api/oidc/status") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ configured: false }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }),
  );

  return render(
    <MemoryRouter initialEntries={["/admin/ops"]}>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/admin/:section" element={<Admin />} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

describe("Admin Ops tab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads ops settings and calls setOpsSettings when Auto-Scale ON is clicked", async () => {
    renderAdmin();

    await waitFor(() => {
      expect(getAdminSettings).toHaveBeenCalled();
    });

    expect(screen.getByText(/secret_key_insecure/i)).toBeTruthy();
    expect(
      screen.getAllByText((_content, el) =>
        /effective now:\s*off/i.test(el?.textContent ?? ""),
      ).length,
    ).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /auto-scale on/i }));

    await waitFor(() => {
      expect(setOpsSettings).toHaveBeenCalledWith({ auto_scale: true });
    });
  });
});
