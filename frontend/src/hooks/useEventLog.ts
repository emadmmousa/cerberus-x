import { useEffect, useMemo, useState } from "react";
import { getSocket, type LogEvent } from "../api/socket";

export type LogEntry = LogEvent & { id: string };

export function useEventLog() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [levelFilter, setLevelFilter] = useState("");
  const [textFilter, setTextFilter] = useState("");

  useEffect(() => {
    const socket = getSocket();

    const onLog = (data: LogEvent) => {
      const entry: LogEntry = {
        ...data,
        level: data.level ?? "INFO",
        id: `${data.timestamp ?? Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      };
      setEntries((prev) => [...prev.slice(-499), entry]);
    };

    socket.on("log", onLog);
    return () => {
      socket.off("log", onLog);
    };
  }, []);

  const filtered = useMemo(() => {
    return entries.filter((entry) => {
      if (levelFilter && entry.level !== levelFilter) return false;
      if (textFilter) {
        const hay = `${entry.message} ${entry.level ?? ""}`.toLowerCase();
        if (!hay.includes(textFilter.toLowerCase())) return false;
      }
      return true;
    });
  }, [entries, levelFilter, textFilter]);

  return {
    entries: filtered,
    levelFilter,
    setLevelFilter,
    textFilter,
    setTextFilter,
  };
}
