import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AuditEventCard } from "../components/AuditEventCard";

describe("AuditEventCard", () => {
  it("requests detail expansion from the parent", () => {
    const onToggle = vi.fn();
    render(
      <MemoryRouter>
        <AuditEventCard
          event={{
            event_type: "DATASET_CONTRIBUTE",
            timestamp: "2026-07-22T10:15:00.000Z",
            actor: "alice",
            actor_role: "operator",
            severity: "info",
            data: { id: "ex-1", posture: "aggressive", license: "CC-BY-4.0" },
          }}
          eventKey="evt-1"
          expanded={false}
          onToggle={onToggle}
        />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: /view details/i }));
    expect(onToggle).toHaveBeenCalledWith("evt-1");
  });

  it("shows detail panel when expanded", () => {
    render(
      <MemoryRouter>
        <ul>
          <AuditEventCard
            event={{
              event_type: "MISSION_STOP",
              actor: "bob",
              data: { job_id: "job-42" },
            }}
            eventKey="evt-2"
            expanded
            onToggle={vi.fn()}
          />
        </ul>
      </MemoryRouter>,
    );

    expect(screen.getByText("Event code")).toBeInTheDocument();
    expect(screen.getByText("MISSION_STOP")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "job-42" })).toHaveAttribute(
      "href",
      "/missions/job-42",
    );
    expect(screen.getByText(/raw event payload/i)).toBeInTheDocument();
  });
});
