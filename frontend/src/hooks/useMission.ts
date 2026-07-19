import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getPlaybook,
  getResults,
  getStatus,
  runPlaybook,
  type PlaybookPhase,
  type ResultRow,
  type RunRequest,
  type TaskStatus,
} from "../api/client";

const ACTIVE_STATES = new Set(["PENDING", "STARTED", "RUNNING"]);

export type PhaseState = "pending" | "running" | "done" | "failed" | "skipped";

export type PhaseView = {
  name: string;
  tools: string[];
  parallel: boolean;
  when?: string | null;
  state: PhaseState;
  taskId?: string;
  error?: string;
  findings: ResultRow[];
};

export function derivePhases(
  pipeline: PlaybookPhase[],
  status: TaskStatus | null,
  resultsByPhase: Record<string, ResultRow[]>,
): PhaseView[] {
  const runState = status?.state;
  const reported = new Map(
    (status?.phases ?? []).map((p) => [p.phase, p]),
  );

  // Index of the phase currently executing: first reported phase that has no
  // saved results yet, while the job is still active.
  const savedPhases = new Set(Object.keys(status?.results ?? {}));
  const staticNames = new Set(pipeline.map((phase) => phase.name));
  const dynamicPhases = [...new Set(
    (status?.phases ?? [])
      .map((phase) => phase.phase)
      .filter((name) => !staticNames.has(name)),
  )].map((name) => ({
    name,
    tools: ["metasploit"],
    parallel: false,
    depends_on: [],
    when: null,
  }));

  let activeAssigned = false;

  return [...pipeline, ...dynamicPhases].map((phase) => {
    const rep = reported.get(phase.name);
    const findings = resultsByPhase[phase.name] ?? [];
    let state: PhaseState = "pending";

    if (
      rep?.error === "No valid tools" ||
      (typeof rep?.error === "string" && rep.error.startsWith("skipped:"))
    ) {
      state = "skipped";
    } else if (savedPhases.has(phase.name)) {
      state = "done";
    } else if (
      findings.length > 0 &&
      (!runState || !ACTIVE_STATES.has(runState))
    ) {
      // Historical/completed jobs may hydrate findings without status.results.
      state = "done";
    } else if (rep && ACTIVE_STATES.has(runState ?? "") && !activeAssigned) {
      state = "running";
      activeAssigned = true;
    } else if (rep) {
      // reported but not yet saved, job no longer active
      state = runState === "FAILURE" ? "failed" : "done";
    }

    if (runState === "FAILURE" && state === "running") {
      state = "failed";
    }

    return {
      name: phase.name,
      tools: phase.tools,
      parallel: phase.parallel,
      when: phase.when,
      state,
      taskId: rep?.task_id,
      error: rep?.error,
      findings,
    };
  });
}

export function useMission() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<TaskStatus | null>(null);
  const [pipeline, setPipeline] = useState<PlaybookPhase[]>([]);
  const [results, setResults] = useState<ResultRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [launchFlash, setLaunchFlash] = useState(false);
  const [activeTarget, setActiveTarget] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getPlaybook()
      .then((data) => setPipeline(data.phases ?? []))
      .catch(() => setPipeline([]));
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const poll = useCallback(
    async (id: string, target: string) => {
      try {
        const [statusData, resultRows] = await Promise.all([
          getStatus(id),
          getResults(target, id).catch(() => [] as ResultRow[]),
        ]);
        setStatus(statusData);
        setResults(resultRows);
        if (!ACTIVE_STATES.has(statusData.state)) {
          stopPolling();
          // one final results sweep after completion (still job-scoped)
          getResults(target, id)
            .then((rows) => setResults(rows))
            .catch(() => undefined);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        stopPolling();
      }
    },
    [stopPolling],
  );

  const startPolling = useCallback(
    (id: string, target: string) => {
      stopPolling();
      void poll(id, target);
      pollRef.current = setInterval(() => void poll(id, target), 2000);
    },
    [poll, stopPolling],
  );

  const launch = useCallback(
    async (request: RunRequest) => {
      setError(null);
      setStatus(null);
      setResults([]);
      try {
        const data = await runPlaybook(request);
        setTaskId(data.task_id);
        setActiveTarget(request.target);
        setLaunchFlash(true);
        setTimeout(() => setLaunchFlash(false), 500);
        startPolling(data.task_id, request.target);
        return data;
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
        throw err;
      }
    },
    [startPolling],
  );

  useEffect(() => () => stopPolling(), [stopPolling]);

  const resultsByPhase = useMemo(() => {
    const grouped: Record<string, ResultRow[]> = {};
    for (const row of results) {
      const key = row.phase ?? "unknown";
      (grouped[key] ??= []).push(row);
    }
    return grouped;
  }, [results]);

  const phases = useMemo(
    () => derivePhases(pipeline, status, resultsByPhase),
    [pipeline, status, resultsByPhase],
  );

  const isActive = status ? ACTIVE_STATES.has(status.state) : false;
  const totalFindings = results.length;
  const completedPhases = phases.filter(
    (p) => p.state === "done" || p.state === "skipped",
  ).length;

  return {
    taskId,
    status,
    error,
    launchFlash,
    launch,
    isActive,
    phases,
    results,
    activeTarget,
    totalFindings,
    completedPhases,
    pipelineLength: pipeline.length,
  };
}
