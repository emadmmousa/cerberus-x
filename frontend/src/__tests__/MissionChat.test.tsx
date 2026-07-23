import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import {
  postMissionChatMessage,
  streamMissionChatMessage,
} from "../api/client";
import { MissionChat } from "../components/MissionChat";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    createMissionChat: vi.fn(async () => ({ chat_id: "c1", messages: [] })),
    getMissionChat: vi.fn(async () => ({ chat_id: "c1", messages: [], draft: null })),
    getChatAgentConfig: vi.fn(async () => ({ llm_reachable: true })),
    fetchBreachIntelStatus: vi.fn(async () => ({ enabled: false })),
    streamMissionChatMessage: vi.fn(),
    postMissionChatMessage: vi.fn(),
  };
});

describe("MissionChat", () => {
  it("does not show OSINT panel when disabled", async () => {
    render(
      <MemoryRouter>
        <MissionChat showOsintPanel={false} chromeless instantChat />
      </MemoryRouter>,
    );
    await screen.findByLabelText("Message");
    expect(screen.queryByText(/OSINT targets/i)).not.toBeInTheDocument();
  });

  it("reports a mission launched by the non-stream fallback", async () => {
    const onMissionLaunched = vi.fn();
    vi.mocked(streamMissionChatMessage).mockRejectedValueOnce(
      new Error("stream transport failed"),
    );
    vi.mocked(postMissionChatMessage).mockResolvedValueOnce({
      reply: "Launching.",
      proposal: {
        ready: true,
        auto_execute: true,
        target: "authorized.example",
        posture: "aggressive",
        nl_goal: "authorized assessment",
      },
      draft: null,
      messages: [],
      mission_launched: {
        task_id: "job-fallback-1",
        target: "authorized.example",
        state: "PENDING",
      },
      launch_error: null,
    });

    render(
      <MemoryRouter>
        <MissionChat instantChat onMissionLaunched={onMissionLaunched} />
      </MemoryRouter>,
    );

    fireEvent.change(await screen.findByLabelText("Message"), {
      target: { value: "Run authorized.example" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(onMissionLaunched).toHaveBeenCalledOnce());
    expect(screen.queryByText(/Confirm mission/i)).not.toBeInTheDocument();
  });
});
