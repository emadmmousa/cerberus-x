import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "../App";

vi.mock("../api/socket", () => ({
  getSocket: () => ({ on: vi.fn(), off: vi.fn() }),
  disconnectSocket: vi.fn(),
}));

function mockFetch() {
  return vi.fn().mockImplementation((url: string) => {
    if (url === "/api/rbac/me") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          authenticated: false,
          role: "operator",
          org_id: "default",
          rbac_enforce: false,
        }),
      });
    }
    if (url === "/auth/status" || url === "/api/oidc/status") {
      return Promise.resolve({
        ok: true,
        json: async () => ({ authenticated: false, configured: false }),
      });
    }
    if (typeof url === "string" && url.startsWith("/api/missions")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ count: 0, missions: [], org_id: "default" }),
      });
    }
    return Promise.resolve({ ok: true, json: async () => ({}) });
  });
}

describe("App", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal("fetch", mockFetch());
  });

  it("shows Missions shell without exploit tabs", async () => {
    render(<App />);
    expect(screen.queryByText(/Exploit Ops/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/MSF Console/i)).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Firebreak/i)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /^missions$/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /^new mission$/i })).toBeInTheDocument();
    });
  });
});
