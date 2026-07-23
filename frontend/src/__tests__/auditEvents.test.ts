import { describe, expect, it } from "vitest";
import {
  auditEventDetails,
  auditEventLabel,
  auditEventSearchBlob,
  auditEventSummary,
  auditStats,
  filterAuditEvents,
  formatAuditPayload,
} from "../lib/auditEvents";

describe("auditEvents", () => {
  it("maps raw event codes to readable labels", () => {
    expect(auditEventLabel("DATASET_CONTRIBUTE")).toBe("Training example contributed");
    expect(auditEventLabel("CUSTOM_EVENT_NAME")).toBe("Custom Event Name");
  });

  it("summarizes dataset contributions", () => {
    expect(
      auditEventSummary({
        event_type: "DATASET_CONTRIBUTE",
        data: { posture: "aggressive", id: "ex-1" },
      }),
    ).toContain("aggressive");
  });

  it("filters by category and search", () => {
    const events = [
      { event_type: "DATASET_CONTRIBUTE", actor: "alice" },
      { event_type: "MISSION_STOP", actor: "bob" },
    ];
    expect(filterAuditEvents(events, "training", "").length).toBe(1);
    expect(filterAuditEvents(events, "all", "bob").length).toBe(1);
    expect(auditStats(events).training).toBe(1);
  });

  it("builds expandable detail rows and searchable payload text", () => {
    const event = {
      event_type: "MISSION_STOP",
      timestamp: "2026-07-22T10:15:00.000Z",
      actor: "admin",
      actor_role: "admin",
      actor_org: "acme",
      source_ip: "10.0.0.5",
      severity: "high",
      data: { job_id: "abc-123", target: "https://lab.example" },
    };
    const rows = auditEventDetails(event);
    expect(rows.some((row) => row.label === "Event code" && row.value === "MISSION_STOP")).toBe(
      true,
    );
    expect(rows.some((row) => row.href === "/missions/abc-123")).toBe(true);
    expect(formatAuditPayload(event.data)).toContain("abc-123");
    expect(auditEventSearchBlob(event)).toContain("abc-123");
  });
});
