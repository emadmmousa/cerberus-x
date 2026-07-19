import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MissionControl } from "../views/MissionControl";

vi.mock("../api/socket", () => ({
  getSocket: () => ({ on: vi.fn(), off: vi.fn() }),
  disconnectSocket: vi.fn(),
}));

function mockFetch() {
  return vi.fn().mockImplementation((url: string) => {
    if (url === "/api/proxy/status") {
      return Promise.resolve({ ok: true, json: async () => ({ configured: true }) });
    }
    if (url === "/api/proxy/settings") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          configured: true,
          source: "env",
          username: "u",
          password_set: true,
          host: "pr.oxylabs.io",
          port: 7777,
          protocol: "http",
          proxy_url_redacted: "http://u:***@pr.oxylabs.io:7777",
        }),
      });
    }
    if (url === "/api/playbook") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          name: "Full Spectrum Attack",
          phases: [
            { name: "recon", tools: ["nmap"], parallel: true, depends_on: [] },
            { name: "vulnerability_scan", tools: ["nuclei"], parallel: false, depends_on: ["recon"] },
          ],
        }),
      });
    }
    if (typeof url === "string" && url.startsWith("/results")) {
      return Promise.resolve({ ok: true, json: async () => [] });
    }
    if (typeof url === "string" && url.startsWith("/status/")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ task_id: "abc", state: "PENDING", phases: [] }),
      });
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({ task_id: "abc", target: "test.com", state: "PENDING" }),
    });
  });
}

describe("MissionControl", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the full phase pipeline from /api/playbook", async () => {
    vi.stubGlobal("fetch", mockFetch());
    render(<MissionControl target="test.com" onTargetChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/recon/i)).toBeInTheDocument();
      expect(screen.getByText(/vulnerability scan/i)).toBeInTheDocument();
    });
  });

  it("launches the unified playbook with use_proxy when toggle enabled", async () => {
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    render(<MissionControl target="test.com" onTargetChange={() => {}} />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/proxy/status");
    });

    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /launch full spectrum/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/run",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            target: "test.com",
            use_proxy: true,
            proxy_protocol: "http",
            evasion: "aggressive",
          }),
        }),
      );
    });
  });
});
