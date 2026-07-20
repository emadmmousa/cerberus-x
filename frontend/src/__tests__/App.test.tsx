import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "../App";

vi.mock("../api/socket", () => ({
  getSocket: () => ({ on: vi.fn(), off: vi.fn() }),
  disconnectSocket: vi.fn(),
}));

function mockFetch() {
  return vi.fn().mockImplementation((url: string) => {
    if (url === "/api/proxy/status") {
      return Promise.resolve({ ok: true, json: async () => ({ configured: false }) });
    }
    if (url === "/api/playbook") {
      return Promise.resolve({
        ok: true,
        json: async () => ({ name: "Full Spectrum Attack", phases: [] }),
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

  it("shows Mission Control only without exploit tabs", () => {
    render(<App />);
    expect(screen.queryByText(/Exploit Ops/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/MSF Console/i)).not.toBeInTheDocument();
    expect(screen.getByText(/CERBERUS-X/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^start$/i })).toBeInTheDocument();
  });
});
