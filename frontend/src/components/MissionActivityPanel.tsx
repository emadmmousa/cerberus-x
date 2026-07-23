import { useEffect, useRef } from "react";
import type { LogEntry } from "../hooks/useEventLog";
import { usePagination } from "../hooks/usePagination";
import { ListPagination } from "./ListPagination";

type Props = {
  entries: LogEntry[];
  levelFilter: string;
  setLevelFilter: (value: string) => void;
  textFilter: string;
  setTextFilter: (value: string) => void;
  followLive?: boolean;
};

const LEVELS = ["", "INFO", "WARNING", "ERROR"] as const;

function formatTime(ts?: number): string {
  if (!ts) return new Date().toLocaleTimeString();
  return new Date(ts * 1000).toLocaleTimeString();
}

export function MissionActivityPanel({
  entries,
  levelFilter,
  setLevelFilter,
  textFilter,
  setTextFilter,
  followLive = false,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const activityPage = usePagination(entries, {
    pageSize: 25,
    pageSizeOptions: [25, 50, 100],
    resetKey: `${levelFilter}|${textFilter}`,
  });

  useEffect(() => {
    if (!followLive || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [entries.length, followLive]);

  return (
    <aside className="mission-activity" aria-label="Activity">
      <div className="mission-activity__head">
        <div>
          <div className="section-label">Activity</div>
          <p className="mission-activity__hint">Live worker and orchestrator events</p>
        </div>
        <span className="mission-activity__count">{entries.length}</span>
      </div>

      <div className="mission-activity__filters">
        <div className="mission-activity__levels" role="group" aria-label="Filter by level">
          {LEVELS.map((level) => (
            <button
              key={level || "all"}
              type="button"
              className={`mission-activity__level${
                levelFilter === level ? " mission-activity__level--active" : ""
              }`}
              onClick={() => setLevelFilter(level)}
            >
              {level || "All"}
            </button>
          ))}
        </div>
        <input
          type="search"
          className="mission-activity__search"
          placeholder="Search logs…"
          value={textFilter}
          onChange={(e) => setTextFilter(e.target.value)}
          aria-label="Search activity"
        />
      </div>

      <div className="mission-activity__scroll log-scroll" ref={scrollRef}>
        {entries.length === 0 && (
          <p className="result-card__meta">No activity yet — events appear as steps run.</p>
        )}
        {activityPage.items.map((entry) => (
          <div key={entry.id} className="log-line">
            <span className="log-line__time">{formatTime(entry.timestamp)}</span>
            <span className={`log-line__lvl log-line__lvl--${entry.level}`}>{entry.level}</span>
            <span>{entry.message}</span>
          </div>
        ))}
      </div>

      <ListPagination
        page={activityPage.page}
        totalPages={activityPage.totalPages}
        total={activityPage.total}
        rangeStart={activityPage.rangeStart}
        rangeEnd={activityPage.rangeEnd}
        pageSize={activityPage.pageSize}
        pageSizeOptions={activityPage.pageSizeOptions}
        onPageChange={activityPage.setPage}
        onPageSizeChange={activityPage.setPageSize}
        label="Activity log pagination"
      />
    </aside>
  );
}
