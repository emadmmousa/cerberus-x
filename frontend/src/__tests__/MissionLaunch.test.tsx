import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MissionLaunch } from "../views/MissionLaunch";

describe("MissionLaunch", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("calls runPlaybook with use_proxy when toggle enabled", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/proxy/status") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ configured: true }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          task_id: "abc",
          target: "test.com",
          state: "PENDING",
        }),
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MissionLaunch target="test.com" onTargetChange={() => {}} />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/proxy/status");
    });

    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /run playbook/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/run",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            target: "test.com",
            use_proxy: true,
            proxy_protocol: "http",
          }),
        }),
      );
    });
  });
});
