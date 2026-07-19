import { useCallback, useEffect, useRef, useState } from "react";
import {
  getStatus,
  runPlaybook,
  type RunRequest,
  type TaskStatus,
} from "../api/client";

const ACTIVE_STATES = new Set(["PENDING", "STARTED", "RUNNING"]);

export function useMission() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<TaskStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [launchFlash, setLaunchFlash] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollStatus = useCallback(
    async (id: string) => {
      try {
        const data = await getStatus(id);
        setStatus(data);
        if (!ACTIVE_STATES.has(data.state)) {
          stopPolling();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        stopPolling();
      }
    },
    [stopPolling],
  );

  const startPolling = useCallback(
    (id: string) => {
      stopPolling();
      void pollStatus(id);
      pollRef.current = setInterval(() => void pollStatus(id), 2000);
    },
    [pollStatus, stopPolling],
  );

  const launch = useCallback(
    async (request: RunRequest) => {
      setError(null);
      setStatus(null);
      try {
        const data = await runPlaybook(request);
        setTaskId(data.task_id);
        setLaunchFlash(true);
        setTimeout(() => setLaunchFlash(false), 400);
        startPolling(data.task_id);
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

  return {
    taskId,
    status,
    error,
    launchFlash,
    launch,
    isActive: status ? ACTIVE_STATES.has(status.state) : false,
  };
}
