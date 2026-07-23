import { describe, expect, it } from "vitest";
import {
  computeTimelineProgress,
  filterMissions,
  formatTimelineProgress,
  missionPostureLabel,
  missionStateLabel,
  missionStats,
  missionStatusKind,
} from "../lib/missionSummary";

describe("missionSummary", () => {
  const rows = [
    { task_id: "a", target: "alpha.com", state: "SUCCESS" },
    { task_id: "b", target: "beta.com", state: "STARTED" },
    { task_id: "c", target: "gamma.com", state: "FAILURE", nl_goal: "sql hunt" },
  ];

  it("classifies running states", () => {
    expect(missionStatusKind("STARTED")).toBe("running");
    expect(missionStateLabel("SUCCESS")).toBe("Complete");
    expect(missionStatusKind("CANCEL_REQUESTED")).toBe("running");
    expect(missionStateLabel("CANCEL_REQUESTED")).toBe("Cancel requested");
  });

  it("filters active missions", () => {
    const active = filterMissions(rows, "", "active");
    expect(active).toHaveLength(1);
    expect(active[0].task_id).toBe("b");
  });

  it("searches target and goal", () => {
    const found = filterMissions(rows, "sql", "all");
    expect(found).toHaveLength(1);
    expect(found[0].task_id).toBe("c");
  });

  it("aggregates stats", () => {
    expect(missionStats(rows)).toEqual({ total: 3, active: 1, done: 1, failed: 1 });
  });

  it("caps timeline progress at 100%", () => {
    expect(computeTimelineProgress(11, 8)).toBe(100);
    expect(computeTimelineProgress(3, 8)).toBe(38);
    expect(computeTimelineProgress(8, 8)).toBe(100);
  });

  it("formats timeline progress copy", () => {
    expect(formatTimelineProgress(11, 12)).toBe("11/12 steps · 92%");
  });

  it("maps posture labels for mission cards", () => {
    expect(missionPostureLabel("aggressive")).toBe("Offensive");
    expect(missionPostureLabel("defensive")).toBe("Defensive");
  });
});
