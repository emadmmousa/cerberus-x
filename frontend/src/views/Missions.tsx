import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  getWorkerReadiness,
  listMissions,
  type MissionProposal,
  type MissionSummaryRow,
  type WorkerReadiness,
} from "../api/client";
import { ManualMissionForm, type ManualMissionPrefill } from "../components/ManualMissionForm";
import {
  MissionChat,
  type MissionChatHandle,
} from "../components/MissionChat";
import { MissionRail } from "../components/MissionRail";
import { MissionsPromptsPanel } from "../components/MissionsPromptsPanel";
import { OsintTabPanel } from "../components/OsintTabPanel";
import { OperationsCommandBar } from "../components/OperationsCommandBar";
import { loadChatOptions, saveChatOptions } from "../lib/chatAgentOptions";
import { buildStrikePromptMessage } from "../lib/strikePromptMessage";
import type { AggressivePrompt } from "../lib/aggressivePrompts";
import type { OsintSeed } from "../lib/osintTargets";
import { usePageVisible } from "../lib/usePageVisible";
import { missionStats } from "../lib/missionSummary";
import { useAuth } from "../providers/AuthProvider";

type Mode = "chat" | "prompts" | "manual" | "osint";
const WORKER_READINESS_POLL_MS = 15_000;

function parseMode(params: URLSearchParams): Mode {
  const value = params.get("mode");
  if (value === "manual") return "manual";
  if (value === "prompts") return "prompts";
  if (value === "osint") return "osint";
  return "chat";
}

export function Missions() {
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const mode = parseMode(params);
  const [rows, setRows] = useState<MissionSummaryRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [prefill, setPrefill] = useState<ManualMissionPrefill | null>(null);
  const [railOpen, setRailOpen] = useState(false);
  const [osintSeeds, setOsintSeeds] = useState<OsintSeed[]>(() => loadChatOptions().osintSeeds);
  const [workerReadiness, setWorkerReadiness] = useState<WorkerReadiness>();
  const pageVisible = usePageVisible();
  const chatRef = useRef<MissionChatHandle | null>(null);

  const stats = useMemo(() => missionStats(rows), [rows]);

  useEffect(() => {
    saveChatOptions({ ...loadChatOptions(), osintSeeds });
  }, [osintSeeds]);

  const loadRail = useCallback(() => {
    listMissions()
      .then((data) => setRows(data.missions ?? []))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!pageVisible) return;
    loadRail();
    const intervalMs = stats.active > 0 ? 5000 : 15000;
    const t = window.setInterval(loadRail, intervalMs);
    return () => window.clearInterval(t);
  }, [loadRail, pageVisible, stats.active]);

  useEffect(() => {
    if (!pageVisible) return;

    let cancelled = false;
    let timer: number | undefined;

    const pollReadiness = async () => {
      try {
        const readiness = await getWorkerReadiness();
        if (!cancelled) setWorkerReadiness(readiness);
      } catch {
        if (!cancelled) {
          setWorkerReadiness({
            status: "unreachable",
            expected_count: 0,
            missing_tasks: [],
            message:
              "Worker readiness is unknown because the endpoint is unreachable. Missions remain available.",
          });
        }
      } finally {
        if (!cancelled) {
          timer = window.setTimeout(pollReadiness, WORKER_READINESS_POLL_MS);
        }
      }
    };

    void pollReadiness();
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [pageVisible]);

  function setMode(next: Mode) {
    const sp = new URLSearchParams(params);
    if (next === "chat") sp.delete("mode");
    else sp.set("mode", next);
    setParams(sp, { replace: true });
  }

  function editManual(proposal: MissionProposal) {
    setPrefill({
      target: proposal.target,
      posture: (proposal.posture as ManualMissionPrefill["posture"]) || "aggressive",
      nl_goal: proposal.nl_goal,
      stealth: (proposal.stealth as ManualMissionPrefill["stealth"]) || "high",
      ai_mode: true,
    });
    setMode("manual");
  }

  function handleSelectPrompt(card: AggressivePrompt) {
    setMode("chat");
    void chatRef.current?.sendPrompt(buildStrikePromptMessage(card.prompt, card.targetProfile));
  }

  return (
    <div className="ops-console">
      <OperationsCommandBar
        mode={mode}
        onModeChange={setMode}
        canOperate={can("operator")}
        activeCount={stats.active}
        totalCount={stats.total}
        doneCount={stats.done}
        failedCount={stats.failed}
        loading={loading}
        railOpen={railOpen}
        onRailToggle={() => setRailOpen((value) => !value)}
        onNewChat={() => void chatRef.current?.newChat()}
        error={error}
        workerReadiness={workerReadiness}
      />

      <div className={`ops-stage${railOpen ? " ops-stage--rail-open" : ""}`}>
        {railOpen && (
          <button
            type="button"
            className="ops-rail-backdrop"
            aria-label="Close mission history"
            onClick={() => setRailOpen(false)}
          />
        )}

        {railOpen && (
          <MissionRail
            id="missions-rail-drawer"
            rows={rows}
            loading={loading}
            error={null}
            onRefresh={loadRail}
            className="ops-rail"
          />
        )}

        <main className="ops-main">
          {can("operator") ? (
            <>
              <div className={`ops-tab-panel${mode !== "chat" ? " ops-tab-panel--hidden" : ""}`}>
                <MissionChat
                  ref={chatRef}
                  compact
                  chromeless
                  instantChat
                  showOsintPanel={false}
                  osintSeeds={osintSeeds}
                  onOsintSeedsChange={setOsintSeeds}
                  onMissionLaunched={() => {
                    loadRail();
                    setRailOpen(false);
                  }}
                  onEditManual={editManual}
                />
              </div>

              {mode === "prompts" && (
                <MissionsPromptsPanel
                  onSelectPrompt={handleSelectPrompt}
                />
              )}

              {mode === "osint" && (
                <OsintTabPanel seeds={osintSeeds} onChange={setOsintSeeds} />
              )}

              {mode === "manual" && (
                <div className="ops-tab-panel">
                  <ManualMissionForm
                    prefill={prefill}
                    navigateOnLaunch={false}
                    onLaunched={() => {
                      setPrefill(null);
                      loadRail();
                      setMode("chat");
                    }}
                  />
                </div>
              )}
            </>
          ) : (
            <section className="panel ops-viewonly">
              <p className="ops-viewonly__title">View only</p>
              <p className="ops-viewonly__text">
                Operator role required to chat or launch missions. Open History to browse past
                runs.
              </p>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
