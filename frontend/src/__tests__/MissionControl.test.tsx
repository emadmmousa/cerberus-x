import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../providers/AuthProvider";
import { ThemeProvider } from "../providers/ThemeProvider";
import { derivePhases } from "../hooks/useMission";
import { ManualMissionForm } from "../components/ManualMissionForm";

vi.mock("../api/socket", () => ({
  getSocket: () => ({ on: vi.fn(), off: vi.fn() }),
  disconnectSocket: vi.fn(),
}));

function mockFetch() {
  return vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    void init;
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
    if (typeof url === "string" && url.startsWith("/api/playbooks")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          playbooks: [
            {
              id: "balanced_offense_defense",
              path: "playbooks/balanced_offense_defense.yaml",
              name: "Balanced Offense + Defense",
              recommended_for: ["balanced"],
            },
          ],
        }),
      });
    }
    if (typeof url === "string" && url.startsWith("/api/playbook")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          name: "Full Spectrum Attack",
          phases: [
            { name: "recon", tools: ["nmap"], parallel: true, depends_on: [] },
            {
              name: "vulnerability_scan",
              tools: ["nuclei"],
              parallel: false,
              depends_on: ["recon"],
            },
          ],
        }),
      });
    }
    if (url === "/api/tools") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          count: 2,
          wired_count: 2,
          tools: [
            {
              name: "nmap",
              category: "port_host",
              risk: "low",
              maturity: "executable",
              description: "scan",
            },
          ],
        }),
      });
    }
    if (url === "/auth/status" || url === "/api/oidc/status") {
      return Promise.resolve({
        ok: true,
        json: async () => ({ authenticated: false, configured: false }),
      });
    }
    if (typeof url === "string" && url.startsWith("/results")) {
      return Promise.resolve({ ok: true, json: async () => [] });
    }
    if (typeof url === "string" && url.startsWith("/status/")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          task_id: "abc",
          state: "PENDING",
          target: "test.com",
          phases: [],
        }),
      });
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({ task_id: "abc", target: "test.com", state: "PENDING" }),
    });
  });
}

function renderNewMission() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <AuthProvider>
          <ManualMissionForm />
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

describe("ManualMissionForm / derivePhases", () => {
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
  });

  it("AI mode maps suffixed phase results to executed steps", () => {
    const phases = derivePhases(
      [],
      {
        task_id: "ai2",
        state: "SUCCESS",
        ai_mode: true,
        phases: [
          { phase: "surface_variants_s0", task_id: "t0" },
          { phase: "recon_s1", task_id: "t1" },
          { phase: "attack_s3", task_id: "t3" },
        ],
        results: {
          attack_s3: [{ tool: "nuclei", findings: [] }],
        },
        ai: {
          steps: [
            {
              phase_name: "attack_s3",
              parallel: false,
              tools: [{ tool: "nuclei", args: ["-silent"] }],
            },
          ],
        },
      },
      {
        attack_s3: [
          {
            target: "example.com",
            tool: "nuclei",
            phase: "attack_s3",
            timestamp: "2026-01-01",
            result: { findings: [{ name: "x" }] },
          },
        ],
      },
    );

    const attack = phases.find((p) => p.name === "attack_s3");
    expect(attack?.state).toBe("done");
    expect(attack?.findings).toHaveLength(1);
    expect(attack?.tools).toEqual(["nuclei"]);
  });

  it("renders launch controls", async () => {
    vi.stubGlobal("fetch", mockFetch());
    renderNewMission();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /start mission/i })).toBeInTheDocument();
    });
  });

  it("launches with proxy when configured", async () => {
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    renderNewMission();

    fireEvent.change(screen.getByLabelText(/^target$/i), {
      target: { value: "test.com" },
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/proxy/status",
        expect.objectContaining({ credentials: "include" }),
      );
    });

    // Proxy defaults on when credentials are configured (see ManualMissionForm useEffect).
    fireEvent.click(screen.getByRole("button", { name: /start mission/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/run",
        expect.objectContaining({
          method: "POST",
          credentials: "include",
          body: JSON.stringify({
            target: "test.com",
            use_proxy: true,
            proxy_protocol: "http",
            evasion: "aggressive",
            ai_mode: false,
            confirm_high_risk: true,
            posture: "aggressive",
            playbook: "playbooks/complete_dark_arsenal.yaml",
          }),
        }),
      );
    });
  });

  it("keeps advanced controls collapsed by default", async () => {
    vi.stubGlobal("fetch", mockFetch());
    renderNewMission();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /start mission/i })).toBeInTheDocument();
    });
    expect(screen.getByLabelText(/^stealth$/i)).toBeInTheDocument();
    expect(screen.queryByText(/proxy settings/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /advanced options/i }));
    expect(screen.getByText(/proxy settings/i)).toBeInTheDocument();
  });
});
