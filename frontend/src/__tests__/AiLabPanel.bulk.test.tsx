import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AiLabPanel } from "../components/AiLabPanel";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>(
    "../api/client",
  );
  return {
    ...actual,
    getAiLabStatus: vi.fn(async () => ({ model: "m", base_model: "b" })),
    getScaffolds: vi.fn(async () => ({ health: [] })),
    getMarketplace: vi.fn(async () => null),
    getEditionStatus: vi.fn(async () => ({})),
    getDatasetExamples: vi.fn(async () => ({
      examples: [
        { id: "a1", label: "A1", prompt: "p1", response: "r1" },
        { id: "a2", label: "A2", prompt: "p2", response: "r2" },
      ],
      guidance: "g",
    })),
    contributeDataset: vi.fn(async () => ({
      persisted: true,
      record: { id: "x" },
    })),
  };
});

import { contributeDataset } from "../api/client";

describe("AiLabPanel bulk", () => {
  it("load all stages examples and submit all contributes each", async () => {
    render(<AiLabPanel />);
    const loadAll = await screen.findByRole("button", {
      name: /load all \(posture\)/i,
    });
    fireEvent.click(loadAll);
    expect(await screen.findByText(/bulk: 2\/2 ready/i)).toBeTruthy();
    fireEvent.click(
      screen.getByRole("button", { name: /submit all \(cc-by\)/i }),
    );
    await waitFor(() => {
      expect(contributeDataset).toHaveBeenCalledTimes(2);
    });
    expect(contributeDataset).toHaveBeenCalledWith({
      prompt: "p1",
      response: "r1",
      posture: "balanced",
      license: "CC-BY-4.0",
      contributor: "mission-control",
    });
    expect(contributeDataset).toHaveBeenCalledWith({
      prompt: "p2",
      response: "r2",
      posture: "balanced",
      license: "CC-BY-4.0",
      contributor: "mission-control",
    });
  });
});
