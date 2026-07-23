import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WorkerReadinessChip } from "../components/OperationsCommandBar";
import { Missions } from "../views/Missions";

const readinessMocks = vi.hoisted(() => ({
  getWorkerReadiness: vi.fn(),
  listMissions: vi.fn(),
  pageVisible: true,
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    getWorkerReadiness: readinessMocks.getWorkerReadiness,
    listMissions: readinessMocks.listMissions,
  };
});

vi.mock("../lib/usePageVisible", () => ({
  usePageVisible: () => readinessMocks.pageVisible,
}));

vi.mock("../providers/AuthProvider", () => ({
  useAuth: () => ({ can: () => false }),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function renderMissions() {
  return render(
    <MemoryRouter>
      <Missions />
    </MemoryRouter>,
  );
}

describe("WorkerReadinessChip", () => {
  beforeEach(() => {
    readinessMocks.pageVisible = true;
    readinessMocks.getWorkerReadiness.mockReset();
    readinessMocks.listMissions.mockReset();
    readinessMocks.listMissions.mockResolvedValue({
      count: 0,
      org_id: "default",
      missions: [],
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders ready worker details", () => {
    render(
      <WorkerReadinessChip
        readiness={{
          status: "ready",
          expected_count: 1,
          missing_tasks: [],
          message: "Workers ready",
        }}
      />,
    );

    expect(screen.getByText(/workers ready/i, { selector: "summary" })).toBeInTheDocument();
    expect(screen.getByText(/workers ready/i, { selector: "p" })).toBeInTheDocument();
  });

  it("renders stale worker remediation", () => {
    render(
      <WorkerReadinessChip
        readiness={{
          status: "stale",
          expected_count: 1,
          missing_tasks: ["run_nmap_task"],
          message: "Restart workers to refresh their task registry.",
        }}
      />,
    );

    expect(screen.getByText(/workers stale/i)).toBeInTheDocument();
    expect(screen.getByText(/run_nmap_task/i)).toBeInTheDocument();
    expect(
      screen.getByText(/restart workers to refresh their task registry/i),
    ).toBeInTheDocument();
  });

  it("renders fallback remediation when unreachable has no message", () => {
    render(
      <WorkerReadinessChip
        readiness={{
          status: "unreachable",
          expected_count: 1,
          missing_tasks: [],
        }}
      />,
    );

    expect(screen.getByText(/workers unreachable/i)).toBeInTheDocument();
    expect(
      screen.getByText(/verify the api, broker, and worker connectivity/i),
    ).toBeInTheDocument();
  });

  it("keeps Missions available when readiness fetch fails", async () => {
    readinessMocks.getWorkerReadiness.mockRejectedValue(new Error("offline"));

    renderMissions();

    expect(await screen.findByText(/workers unreachable/i)).toBeInTheDocument();
    expect(screen.getByText(/view only/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /history/i })).toBeInTheDocument();
  });

  it("polls only while visible and never overlaps readiness requests", async () => {
    vi.useFakeTimers();
    readinessMocks.pageVisible = false;
    const first = deferred<{
      status: "ready";
      expected_count: number;
      missing_tasks: string[];
      message: string;
    }>();
    const second = deferred<{
      status: "ready";
      expected_count: number;
      missing_tasks: string[];
      message: string;
    }>();
    readinessMocks.getWorkerReadiness
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);

    const view = renderMissions();
    expect(readinessMocks.getWorkerReadiness).not.toHaveBeenCalled();

    readinessMocks.pageVisible = true;
    view.rerender(
      <MemoryRouter>
        <Missions />
      </MemoryRouter>,
    );
    expect(readinessMocks.getWorkerReadiness).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(readinessMocks.getWorkerReadiness).toHaveBeenCalledTimes(1);

    await act(async () => {
      first.resolve({
        status: "ready",
        expected_count: 1,
        missing_tasks: [],
        message: "Workers ready",
      });
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(15_000);
    });
    expect(readinessMocks.getWorkerReadiness).toHaveBeenCalledTimes(2);

    readinessMocks.pageVisible = false;
    view.rerender(
      <MemoryRouter>
        <Missions />
      </MemoryRouter>,
    );
    await act(async () => {
      second.resolve({
        status: "ready",
        expected_count: 1,
        missing_tasks: [],
        message: "Workers ready",
      });
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(readinessMocks.getWorkerReadiness).toHaveBeenCalledTimes(2);
  });
});
