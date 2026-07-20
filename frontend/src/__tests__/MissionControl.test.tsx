import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { derivePhases } from "../hooks/useMission";
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

  it("adds reported automated impact phases to the timeline", () => {
    const phases = derivePhases(
      [{ name: "recon", tools: ["nmap"], parallel: false, depends_on: [] }],
      {
        task_id: "abc",
        state: "RUNNING",
        phases: [{ phase: "proof_of_impact", task_id: "impact-task" }],
      },
      {},
    );

    expect(phases).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          name: "proof_of_impact",
          state: "running",
          taskId: "impact-task",
        }),
      ]),
    );
  });

  it("AI mode shows planned tools instead of the YAML playbook", () => {
    const phases = derivePhases(
      [
        { name: "recon", tools: ["masscan", "nmap"], parallel: true, depends_on: [] },
        { name: "vulnerability_scan", tools: ["nuclei"], parallel: false, depends_on: ["recon"] },
      ],
      {
        task_id: "ai1",
        state: "FAILURE",
        ai_mode: true,
        phases: [{ phase: "Reconnaissance", task_id: "grp-1" }],
        ai: {
          steps: [
            {
              phase_name: "Reconnaissance",
              parallel: true,
              tools: [
                { tool: "masscan", args: ["-p80,443"] },
                { tool: "nmap", args: ["-sV"] },
              ],
            },
          ],
        },
      },
      {},
    );

    expect(phases.map((p) => p.name)).toEqual(["Reconnaissance"]);
    expect(phases[0].tools).toEqual(["masscan", "nmap"]);
    expect(phases[0].state).toBe("failed");
    expect(phases.some((p) => p.tools.includes("ai"))).toBe(false);
  });

  it("renders the full phase pipeline from /api/playbook", async () => {
    vi.stubGlobal("fetch", mockFetch());
    render(<MissionControl target="test.com" onTargetChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/reconnaissance/i)).toBeInTheDocument();
      expect(screen.getByText(/vulnerability checks/i)).toBeInTheDocument();
    });
  });

  it("launches with Start after enabling proxy in Options", async () => {
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    render(<MissionControl target="test.com" onTargetChange={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: /^options$/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/proxy/status");
    });

    fireEvent.click(screen.getByLabelText(/^proxy$/i));
    fireEvent.click(screen.getByRole("button", { name: /^start$/i }));

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
            ai_mode: false,
            confirm_high_risk: true,
          }),
        }),
      );
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/results?target=test.com&job_id=abc");
    });
  });

  it("keeps advanced controls collapsed by default", async () => {
    vi.stubGlobal("fetch", mockFetch());
    render(<MissionControl target="" onTargetChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /^start$/i })).toBeInTheDocument();
    });
    expect(screen.queryByLabelText(/^stealth$/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^options$/i }));
    expect(screen.getByLabelText(/^stealth$/i)).toBeInTheDocument();
  });
});
