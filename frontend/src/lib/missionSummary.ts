import type { MissionSummaryRow } from "../api/client";

export type MissionStatusKind = "success" | "failure" | "cancelled" | "running" | "pending";

export type MissionFilter = "all" | "active" | "done" | "failed";

export function missionStatusKind(state?: string): MissionStatusKind {
  const s = (state ?? "").toUpperCase();
  if (s === "SUCCESS") return "success";
  if (s === "CANCELLED") return "cancelled";
  if (s === "FAILURE") return "failure";
  if (s === "STARTED" || s === "PROGRESS" || s === "RETRY" || s === "PENDING" || s === "RUNNING" || s === "CANCEL_REQUESTED")
    return "running";
  return "pending";
}

export function missionStateLabel(state?: string): string {
  if ((state ?? "").toUpperCase() === "CANCEL_REQUESTED") return "Cancel requested";
  const kind = missionStatusKind(state);
  if (kind === "success") return "Complete";
  if (kind === "cancelled") return "Cancelled";
  if (kind === "failure") return "Failed";
  if (kind === "running") return "Running";
  return "Queued";
}

export function filterMissions(
  rows: MissionSummaryRow[],
  query: string,
  filter: MissionFilter,
): MissionSummaryRow[] {
  const q = query.trim().toLowerCase();
  return rows.filter((row) => {
    const kind = missionStatusKind(row.state);
    if (filter === "active" && kind !== "running") return false;
    if (filter === "done" && kind !== "success") return false;
    if (filter === "failed" && kind !== "failure") return false;
    if (!q) return true;
    const blob = [row.target, row.task_id, row.nl_goal, row.error, row.posture]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return blob.includes(q);
  });
}

export function missionStats(rows: MissionSummaryRow[]) {
  let active = 0;
  let done = 0;
  let failed = 0;
  for (const row of rows) {
    const kind = missionStatusKind(row.state);
    if (kind === "running") active += 1;
    else if (kind === "success") done += 1;
    else if (kind === "failure") failed += 1;
  }
  return { total: rows.length, active, done, failed };
}

export function shortTaskId(taskId: string): string {
  if (taskId.length <= 10) return taskId;
  return `${taskId.slice(0, 8)}…`;
}

const POSTURE_LABELS: Record<string, string> = {
  aggressive: "Offensive",
  defensive: "Defensive",
  balanced: "Balanced",
};

export function missionPostureLabel(posture?: string | null): string {
  const key = (posture ?? "").trim().toLowerCase();
  return POSTURE_LABELS[key] ?? posture ?? "";
}

/** Progress against the live execution timeline (never above 100%). */
export function computeTimelineProgress(completed: number, total: number): number {
  if (total <= 0) return 0;
  return Math.min(100, Math.round((completed / total) * 100));
}

export function formatTimelineProgress(completed: number, total: number): string {
  const pct = computeTimelineProgress(completed, total);
  if (total <= 0) return `${completed} steps`;
  return `${completed}/${total} steps · ${pct}%`;
}
