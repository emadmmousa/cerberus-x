import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { exportFindingsReport, listFindings } from "../api/client";
import { MissionFindingsPanel } from "../components/MissionFindingsPanel";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    listFindings: vi.fn(),
    exportFindingsReport: vi.fn(),
  };
});

describe("MissionFindingsPanel", () => {
  it("renders findings ordered by severity and supports export", async () => {
    vi.mocked(listFindings).mockResolvedValueOnce({
      count: 2,
      total: 2,
      limit: 100,
      offset: 0,
      findings: [
        {
          id: 2,
          fingerprint: "b",
          target: "lab.example",
          title: "Open port 443/https",
          severity: "info",
          tool: "nmap",
          observation_count: 1,
          evidence: [{ available: true, phase: "recon", result_id: 1 }],
        },
        {
          id: 1,
          fingerprint: "a",
          target: "lab.example",
          title: "SQL injection confirmed",
          severity: "high",
          tool: "sqlmap",
          endpoint: "https://lab.example/login",
          observation_count: 2,
          evidence: [{ available: true, phase: "exploit", result_id: 2 }],
        },
      ],
    });
    vi.mocked(exportFindingsReport).mockResolvedValueOnce("# Findings report\n");

    render(<MissionFindingsPanel jobId="job-1" target="lab.example" />);

    await screen.findByText("SQL injection confirmed");
    expect(screen.getByText("Open port 443/https")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Export Markdown" }));
    await waitFor(() => {
      expect(exportFindingsReport).toHaveBeenCalledWith("job-1", "markdown");
    });
  });

  it("shows empty state when no findings exist", async () => {
    vi.mocked(listFindings).mockResolvedValueOnce({
      count: 0,
      total: 0,
      limit: 100,
      offset: 0,
      findings: [],
    });

    render(<MissionFindingsPanel jobId="job-empty" />);

    expect(
      await screen.findByText(/No normalized findings yet/i),
    ).toBeInTheDocument();
  });
});
