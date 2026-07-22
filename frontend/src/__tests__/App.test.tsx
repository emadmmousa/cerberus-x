import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "../App";

vi.mock("../api/socket", () => ({
  getSocket: () => ({ on: vi.fn(), off: vi.fn() }),
  disconnectSocket: vi.fn(),
}));

function mockFetch() {
  return vi.fn().mockImplementation((url: string, init?: RequestInit) => {
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
    if (typeof url === "string" && url.startsWith("/api/chat/missions")) {
      if (init?.method === "POST" && url === "/api/chat/missions") {
        return Promise.resolve({
          ok: true,
          status: 201,
          json: async () => ({ chat_id: "chat-test" }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          id: "chat-test",
          messages: [],
          draft: null,
          mission_ids: [],
        }),
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

  it("shows the public landing page at the root path", async () => {
    render(<App />);
    expect(screen.queryByText(/Exploit Ops/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/MSF Console/i)).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Break in first/i)).toBeInTheDocument();
      // Unauthenticated visitors get marketing CTAs, not the console.
      expect(screen.getAllByRole("link", { name: /start free/i }).length).toBeGreaterThan(0);
      expect(screen.getByText(/One authorized target included/i)).toBeInTheDocument();
    });
  });
});
