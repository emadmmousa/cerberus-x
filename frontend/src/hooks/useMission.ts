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
import { computeTimelineProgress } from "../lib/missionSummary";

const ACTIVE_STATES = new Set(["PENDING", "STARTED", "RUNNING", "CANCEL_REQUESTED"]);

export function isMissionActive(state?: string): boolean {
  return ACTIVE_STATES.has(state ?? "");
}

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

/** Fold dynamic decision-engine phases into their parent timeline step. */
export function foldPhaseKey(phase: string): string {
  if (phase.startsWith("proof_of_impact_")) return "proof_of_impact";
  if (phase.startsWith("access_gained_")) return "access_gained";
  if (phase.startsWith("post_exploitation_")) return "post_exploitation";
  return phase;
}

export function isFoldedChildPhase(name: string, parentNames: Set<string>): boolean {
  const parent = foldPhaseKey(name);
  return parent !== name && parentNames.has(parent);
}

/** Keep the newest row per tool (legacy missions re-ran the same tool). */
export function dedupeFindingsByTool(rows: ResultRow[]): ResultRow[] {
  const byTool = new Map<string, ResultRow>();
  for (const row of rows) {
    const tool = row.tool || "unknown";
    const prev = byTool.get(tool);
    if (!prev) {
      byTool.set(tool, row);
      continue;
    }
    const prevTs = Number(prev.timestamp) || 0;
    const nextTs = Number(row.timestamp) || 0;
    if (nextTs >= prevTs) byTool.set(tool, row);
  }
  return Array.from(byTool.values());
}

/** Collapse repeated AI plan steps that reused the same phase_name. */
export function collapseAiSteps<
  T extends {
    phase_name?: string | null;
    stop?: boolean;
    tools?: { tool: string }[];
    source?: string;
    consensus?: {
      candidates?: number;
      confidence?: number;
      sources?: Array<string | null>;
      mode?: string;
    };
  },
>(steps: T[]): T[] {
  const byName = new Map<string, T>();
  for (const step of steps) {
    if (step.stop || !(step.tools?.length || step.phase_name)) continue;
    const name = step.phase_name || "ai_phase";
    byName.set(name, step);
  }
  return Array.from(byName.values());
}

export function derivePhases(
  pipeline: PlaybookPhase[],
  status: TaskStatus | null,
  resultsByPhase: Record<string, ResultRow[]>,
): PhaseView[] {
  const runState = status?.state;
  const reported = new Map(
    (status?.phases ?? []).map((p) => [p.phase, p]),
  );

  const savedPhases = new Set([
    ...Object.keys(status?.results ?? {}).map((name) => foldPhaseKey(name)),
    ...Object.keys(resultsByPhase),
  ]);

  type PipelineEntry = {
    name: string;
    tools: string[];
    parallel: boolean;
    depends_on: string[];
    when: string | null;
  };

  const toolsFromAiStep = (
    phaseName: string,
    steps: NonNullable<TaskStatus["ai"]>["steps"],
  ): string[] => {
    if (!steps?.length) return [];
    for (let i = steps.length - 1; i >= 0; i -= 1) {
      const step = steps[i];
      if (step?.stop) continue;
      const name = step.phase_name || "";
      if (name === phaseName) {
        return Array.from(
          new Set((step.tools ?? []).map((t) => t.tool).filter(Boolean)),
        );
      }
    }
    const base = phaseName.replace(/_s\d+$/, "");
    for (let i = steps.length - 1; i >= 0; i -= 1) {
      const step = steps[i];
      if (step?.stop) continue;
      const name = step.phase_name || "";
      if (name === base || name.startsWith(`${base}_s`)) {
        return Array.from(
          new Set((step.tools ?? []).map((t) => t.tool).filter(Boolean)),
        );
      }
    }
    return [];
  };

  // AI Mode: timeline follows executed phases; ai.steps supply tool chips.
  let effectivePipeline: PlaybookPhase[] = pipeline;
  if (status?.ai_mode) {
    const aiStepsRaw = (status.ai?.steps ?? []).filter(
      (step) => !step.stop && (step.tools?.length || step.phase_name),
    );
    const planned = new Map<string, PipelineEntry>();
    for (const step of aiStepsRaw) {
      const name = step.phase_name || "ai_phase";
      planned.set(name, {
        name,
        tools: Array.from(
          new Set((step.tools ?? []).map((t) => t.tool).filter(Boolean)),
        ),
        parallel: Boolean(step.parallel),
        depends_on: [],
        when: null,
      });
    }

    const executedNames = (status.phases ?? [])
      .map((phase) => phase.phase)
      .filter(Boolean);
    const orderedNames =
      executedNames.length > 0
        ? [...executedNames]
        : Array.from(planned.keys());

    for (const name of planned.keys()) {
      if (!orderedNames.includes(name)) {
        orderedNames.push(name);
      }
    }

    const parentNames = new Set(
      [...orderedNames, ...planned.keys()].map((name) => foldPhaseKey(name)),
    );

    effectivePipeline = orderedNames
      .filter((name) => !isFoldedChildPhase(name, parentNames))
      .map((name) => {
        const canonical = foldPhaseKey(name);
        const fromPlan = planned.get(name) ?? planned.get(canonical);
        return {
          name: canonical,
          tools: fromPlan?.tools.length
            ? fromPlan.tools
            : toolsFromAiStep(canonical, status.ai?.steps),
          parallel: fromPlan?.parallel ?? false,
          depends_on: [] as string[],
          when: null as string | null,
        };
      })
      .filter((phase, index, list) =>
        list.findIndex((entry) => entry.name === phase.name) === index,
      );
  }

  const staticNames = new Set(effectivePipeline.map((phase) => phase.name));
  const dynamicPhases = status?.ai_mode
    ? []
    : [...new Set(
        (status?.phases ?? [])
          .map((phase) => phase.phase)
          .filter(
            (name) =>
              !staticNames.has(foldPhaseKey(name)) &&
              !isFoldedChildPhase(name, staticNames),
          ),
      )].map((name) => ({
        name: foldPhaseKey(name),
        tools: ["adaptive"],
        parallel: false,
        depends_on: [] as string[],
        when: null as string | null,
      }));

  const reportedForPhase = (name: string) => {
    const direct = reported.get(name);
    if (direct) return direct;
    for (const [phaseName, info] of reported) {
      if (foldPhaseKey(phaseName) === name) return info;
    }
    return undefined;
  };

  let activeAssigned = false;

  return [...effectivePipeline, ...dynamicPhases].map((phase) => {
    const rep = reportedForPhase(phase.name);
    const findings = dedupeFindingsByTool(resultsByPhase[phase.name] ?? []);
    const findingTools = findings.map((row) => row.tool).filter(Boolean);
    const tools = Array.from(new Set([...phase.tools, ...findingTools]));
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
      state = runState === "FAILURE" ? "failed" : "done";
    } else if (findings.length > 0) {
      state = "done";
    }

    if (runState === "FAILURE" && state === "running") {
      state = "failed";
    }

    return {
      name: phase.name,
      tools,
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

  const refreshPipeline = useCallback((playbookPath?: string) => {
    getPlaybook(playbookPath)
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
        if (!isMissionActive(statusData.state)) {
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

  const attachMission = useCallback(
    async (id: string) => {
      setError(null);
      setTaskId(id);
      try {
        const statusData = await getStatus(id);
        setStatus(statusData);
        const target = statusData.target || "";
        setActiveTarget(target || null);
        if (target) {
          const rows = await getResults(target, id).catch(() => [] as ResultRow[]);
          setResults(rows);
          if (isMissionActive(statusData.state)) {
            startPolling(id, target);
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [startPolling],
  );

  useEffect(() => () => stopPolling(), [stopPolling]);

  const resultsByPhase = useMemo(() => {
    const grouped: Record<string, ResultRow[]> = {};
    for (const row of results) {
      const key = foldPhaseKey(row.phase ?? "unknown");
      (grouped[key] ??= []).push(row);
    }
    return grouped;
  }, [results]);

  const phases = useMemo(
    () => derivePhases(pipeline, status, resultsByPhase),
    [pipeline, status, resultsByPhase],
  );

  const isActive = status ? isMissionActive(status.state) : false;
  const totalFindings = results.length;
  const completedPhases = phases.filter(
    (p) => p.state === "done" || p.state === "skipped",
  ).length;
  const timelineLength = phases.length;
  const progressPercent = computeTimelineProgress(completedPhases, timelineLength);

  return {
    taskId,
    status,
    error,
    launchFlash,
    launch,
    attachMission,
    refreshPipeline,
    isActive,
    phases,
    results,
    activeTarget,
    totalFindings,
    completedPhases,
    timelineLength,
    progressPercent,
    pipelineLength: pipeline.length,
  };
}
