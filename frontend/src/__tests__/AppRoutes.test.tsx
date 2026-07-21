import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../providers/AuthProvider";
import { ThemeProvider } from "../providers/ThemeProvider";
import { AppRoutes } from "../routes";

vi.mock("../api/socket", () => ({
  getSocket: () => ({ on: vi.fn(), off: vi.fn() }),
  disconnectSocket: vi.fn(),
}));

function stubSession(role = "operator", enforce = false) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url === "/api/rbac/me") {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            authenticated: true,
            user: "alice",
            role,
            org_id: "default",
            rbac_enforce: enforce,
          }),
        });
      }
      if (url === "/auth/status") {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            authenticated: true,
            user: "alice",
            role,
            org_id: "default",
          }),
        });
      }
      if (url === "/api/oidc/status") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ configured: false }),
        });
      }
      if (typeof url === "string" && url.startsWith("/api/missions")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ count: 0, missions: [], org_id: "default" }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }),
  );
}

describe("AppRoutes", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows Missions nav and list for operator", async () => {
    stubSession("operator", false);
    render(
      <MemoryRouter initialEntries={["/missions"]}>
        <ThemeProvider>
          <AuthProvider>
            <AppRoutes />
          </AuthProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/Firebreak/i)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /^missions$/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /^ai lab$/i })).toBeInTheDocument();
    });
  });

  it("hides AI Lab nav for viewer when RBAC enforce is on", async () => {
    stubSession("viewer", true);
    render(
      <MemoryRouter initialEntries={["/missions"]}>
        <ThemeProvider>
          <AuthProvider>
            <AppRoutes />
          </AuthProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /^missions$/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole("link", { name: /^ai lab$/i })).not.toBeInTheDocument();
  });

  it("renders Login route", async () => {
    stubSession("operator", false);
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <ThemeProvider>
          <AuthProvider>
            <AppRoutes />
          </AuthProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/sign in/i)).toBeInTheDocument();
    });
  });
});
