import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cancelMission, retryMission } from "../api/client";
import { isMissionActive } from "../hooks/useMission";
import { missionStateLabel } from "../lib/missionSummary";
import { MissionDetail } from "../views/MissionDetail";

const attachMission = vi.fn();
let missionState = "STARTED";

vi.mock("../hooks/useMission", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../hooks/useMission")>();
  return {
    ...actual,
    collapseAiSteps: () => [],
    useMission: () => ({
    status: {
      task_id: "mission-1",
      target: "example.test",
      state: missionState,
      phases: [],
    },
    error: null,
    attachMission,
    isActive: missionState === "STARTED" || missionState === "PENDING",
    phases: [],
    results: [],
    activeTarget: "example.test",
    completedPhases: 0,
    timelineLength: 0,
    progressPercent: 0,
    }),
  };
});

vi.mock("../components/BlackboardPanel", () => ({ BlackboardPanel: () => null }));
vi.mock("../components/MissionActivityPanel", () => ({ MissionActivityPanel: () => null }));
vi.mock("../components/MissionPhaseNav", () => ({ MissionPhaseNav: () => null }));
vi.mock("../components/MissionSummary", () => ({ MissionSummary: () => null }));
vi.mock("../components/PhaseCard", () => ({ PhaseCard: () => null }));
vi.mock("../components/PageHero", () => ({
  PageHero: ({
    actions,
    status,
  }: {
    actions: ReactNode;
    status: { label: string };
  }) => (
    <div>
      <span>{status.label}</span>
      {actions}
    </div>
  ),
}));
vi.mock("../hooks/useEventLog", () => ({
  useEventLog: () => ({
    entries: [],
    levelFilter: "all",
    setLevelFilter: vi.fn(),
    textFilter: "",
    setTextFilter: vi.fn(),
  }),
}));

function renderMissionDetail() {
  return render(
    <MemoryRouter initialEntries={["/missions/mission-1"]}>
      <Routes>
        <Route path="/missions/:id" element={<MissionDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Mission lifecycle controls", () => {
  beforeEach(() => {
    missionState = "STARTED";
    attachMission.mockReset();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) =>
        Promise.resolve({
          ok: true,
          json: async () =>
            url.endsWith("/retry")
              ? { task_id: "mission-2", retried_from: "mission-1", state: "PENDING" }
              : { task_id: "mission-1", state: "CANCEL_REQUESTED", revoked_task_ids: [] },
        }),
      ),
    );
  });

  it("posts cancellation and explains it is cooperative", async () => {
    renderMissionDetail();

    fireEvent.click(screen.getByRole("button", { name: /cancel mission/i }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/missions/mission-1/cancel",
        expect.objectContaining({ method: "POST", credentials: "include" }),
      );
    });
    expect(
      screen.getByText(/cancel requested.*current phase.*finish collection/i),
    ).toBeInTheDocument();
  });

  it("retries failed missions as a new mission", async () => {
    missionState = "FAILURE";
    renderMissionDetail();

    fireEvent.click(screen.getByRole("button", { name: /retry mission/i }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/missions/mission-1/retry",
        expect.objectContaining({ method: "POST", credentials: "include" }),
      );
    });
    expect(attachMission).toHaveBeenCalledWith("mission-2");
  });

  it("labels a pending cancellation explicitly", () => {
    missionState = "CANCEL_REQUESTED";
    renderMissionDetail();

    expect(screen.getByText("Cancel requested")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cancel mission/i })).not.toBeInTheDocument();
  });

  it("keeps polling while cancellation is pending", () => {
    expect(isMissionActive("CANCEL_REQUESTED")).toBe(true);
    expect(isMissionActive("CANCELLED")).toBe(false);
  });

  it("labels terminal cancellation as cancelled", () => {
    expect(missionStateLabel("CANCELLED")).toBe("Cancelled");
  });

  it("uses the mission lifecycle API helpers", async () => {
    await cancelMission("mission-1");
    await retryMission("mission-1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/missions/mission-1/cancel",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
    expect(fetch).toHaveBeenCalledWith(
      "/api/missions/mission-1/retry",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });
});
