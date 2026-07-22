import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  createMissionChat,
  dismissMissionChatDraft,
  getMissionChat,
  launchMissionChat,
  postMissionChatMessage,
  registerCustomTool,
  streamMissionChatMessage,
  type ChatMessage,
  type CustomToolDraft,
  type MissionProposal,
} from "../api/client";
import { useStreamingText } from "../lib/useStreamingText";

const ACTIVE_CHAT_STORAGE_KEY = "firebreak:activeChatId";

type Props = {
  onMissionLaunched?: () => void;
  onEditManual?: (proposal: MissionProposal) => void;
};

const SUGGESTIONS = [
  "Plan a full red-team process for an authorized web app",
  "What payloads should I try for a reflected XSS?",
  "Design an aggressive recon → exploitation chain",
  "Harden a target after we prove impact",
];

export function MissionChat({ onMissionLaunched, onEditManual }: Props) {
  const [chatId, setChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState<MissionProposal | null>(null);
  const [toolDraft, setToolDraft] = useState<CustomToolDraft | null>(null);
  const [toolNote, setToolNote] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const {
    text: liveText,
    push: pushLive,
    flush: flushLive,
    reset: resetLive,
  } = useStreamingText();
  const [error, setError] = useState<string | null>(null);
  const [launchError, setLaunchError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const ensureChat = useCallback(async () => {
    if (chatId) return chatId;
    const created = await createMissionChat();
    setChatId(created.chat_id);
    return created.chat_id;
  }, [chatId]);

  useEffect(() => {
    let cancelled = false;
    async function bootChat() {
      const stored = localStorage.getItem(ACTIVE_CHAT_STORAGE_KEY);
      if (stored) {
        try {
          const thread = await getMissionChat(stored);
          if (!cancelled) {
            setChatId(stored);
            setMessages(thread.messages ?? []);
            setDraft(thread.draft ?? null);
            return;
          }
        } catch {
          localStorage.removeItem(ACTIVE_CHAT_STORAGE_KEY);
        }
      }
      try {
        const created = await createMissionChat();
        if (!cancelled) {
          setChatId(created.chat_id);
          localStorage.setItem(ACTIVE_CHAT_STORAGE_KEY, created.chat_id);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to start chat");
        }
      }
    }
    void bootChat();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (chatId) {
      localStorage.setItem(ACTIVE_CHAT_STORAGE_KEY, chatId);
    }
  }, [chatId]);

  useEffect(() => {
    const el = bottomRef.current;
    if (el && typeof el.scrollIntoView === "function") {
      // Instant follow while streaming (fires ~60fps); smooth for settled state.
      el.scrollIntoView({ behavior: streaming ? "auto" : "smooth" });
    }
  }, [messages, draft, liveText, streaming]);

  const send = useCallback(
    async (text: string) => {
      const clean = text.trim();
      if (!clean || busy) return;
      setBusy(true);
      setError(null);
      setLaunchError(null);
      setInput("");
      // Optimistic user bubble + live assistant bubble.
      setMessages((prev) => [...prev, { role: "user", content: clean, ts: Date.now() }]);
      resetLive();
      setStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const id = await ensureChat();
        await streamMissionChatMessage(id, clean, {
          signal: controller.signal,
          onDelta: (delta) => pushLive(delta),
          onDone: (payload) => {
            setMessages(payload.messages ?? []);
            setDraft(payload.draft ?? (payload.proposal?.ready ? payload.proposal : null));
            if (payload.toolProposal) {
              setToolDraft(payload.toolProposal);
              setToolNote(null);
            }
            resetLive();
          },
          onError: (msg) => setError(msg),
        });
      } catch (err) {
        if (controller.signal.aborted) {
          // User stopped the stream — keep whatever streamed and persist via
          // the non-streaming endpoint so the thread stays consistent.
          resetLive();
        } else {
          // Transport failure: fall back to the non-streaming endpoint.
          try {
            const id = await ensureChat();
            const res = await postMissionChatMessage(id, clean);
            setMessages(res.messages ?? []);
            setDraft(res.draft ?? (res.proposal?.ready ? res.proposal : null));
          } catch (e2) {
            setError(e2 instanceof Error ? e2.message : "Send failed");
            setInput(clean);
          }
          resetLive();
        }
      } finally {
        setStreaming(false);
        setBusy(false);
        abortRef.current = null;
      }
    },
    [busy, ensureChat, pushLive, resetLive],
  );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(input);
  }

  function onStop() {
    flushLive();
    abortRef.current?.abort();
  }

  async function onLaunch() {
    if (!chatId || !draft?.ready || busy) return;
    setBusy(true);
    setLaunchError(null);
    try {
      const res = await launchMissionChat(chatId, {
        confirm_high_risk: draft.posture !== "defensive",
      });
      setMessages(res.messages ?? []);
      setDraft(null);
      onMissionLaunched?.();
    } catch (err) {
      setLaunchError(err instanceof Error ? err.message : "Launch failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDismiss() {
    if (!chatId) return;
    try {
      await dismissMissionChatDraft(chatId);
      setDraft(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dismiss failed");
    }
  }

  async function onApproveTool() {
    if (!toolDraft || busy) return;
    setBusy(true);
    setToolNote(null);
    try {
      const res = await registerCustomTool(toolDraft);
      setToolNote(
        `Approved — "${res.tool.name}" is now available to the planner.`,
      );
      setToolDraft(null);
    } catch (err) {
      setToolNote(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  async function onNewChat() {
    abortRef.current?.abort();
    setBusy(true);
    setError(null);
    setLaunchError(null);
    try {
      const created = await createMissionChat();
      setChatId(created.chat_id);
      localStorage.setItem(ACTIVE_CHAT_STORAGE_KEY, created.chat_id);
      setMessages([]);
      setDraft(null);
      setToolDraft(null);
      setToolNote(null);
      resetLive();
      setInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start chat");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel mission-chat" aria-label="Mission chat">
      <div className="page-head">
        <div className="page-head__text">
          <div className="section-label">Firebreak agent</div>
          <p className="section-sub">
            Ask anything cyber, plan the attack, or launch an authorized mission.
          </p>
        </div>
        <button type="button" className="btn" onClick={() => void onNewChat()}>
          New chat
        </button>
      </div>

      <div className="mission-chat__thread" role="log" aria-live="polite">
        {messages.length === 0 && !liveText && (
          <div className="mission-chat__welcome">
            <p className="empty-state">
              I’m your red-team co-pilot. Plan a chain, ask about payloads, or name an
              authorized target to launch.
            </p>
            <div className="mission-chat__suggestions">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="chip chip--action"
                  disabled={busy}
                  onClick={() => void send(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={`${m.ts ?? i}-${m.role}`}
            className={`mission-chat__bubble mission-chat__bubble--${m.role}`}
          >
            <div className="mission-chat__role">{m.role}</div>
            <div className="mission-chat__content">{m.content}</div>
            {m.mission_card && (
              <div className="mission-chat__running">
                <span className="badge badge--ok">Running</span>{" "}
                <span className="mono">{m.mission_card.target}</span>
                <Link className="link-btn" to={`/missions/${m.mission_card.task_id}`}>
                  Open detail
                </Link>
              </div>
            )}
          </div>
        ))}

        {streaming && (
          <div className="mission-chat__bubble mission-chat__bubble--assistant">
            <div className="mission-chat__role">assistant</div>
            <div className="mission-chat__content">
              {liveText || <span className="mission-chat__typing">▍</span>}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {toolDraft && (
        <div
          className="mission-chat__confirm"
          role="region"
          aria-label="Approve custom tool"
        >
          <div className="section-label">New tool proposal</div>
          <ul className="mission-chat__confirm-list">
            <li>
              <strong>Name</strong> <span className="mono">{toolDraft.name}</span>
            </li>
            <li>
              <strong>Runs</strong>{" "}
              <span className="mono">
                {toolDraft.binary} {toolDraft.args_template.join(" ")}
              </span>
            </li>
            {toolDraft.description && (
              <li>
                <strong>Purpose</strong> {toolDraft.description}
              </li>
            )}
            <li>
              <strong>Risk</strong> {toolDraft.risk ?? "medium"}
            </li>
          </ul>
          <p className="section-sub">
            Approving registers this wrapper so the AI planner can schedule it in
            missions. It runs as a direct command (no shell) on your worker.
          </p>
          <div className="mission-chat__confirm-actions">
            <button
              type="button"
              className="btn btn--primary"
              disabled={busy}
              onClick={() => void onApproveTool()}
            >
              Approve &amp; register
            </button>
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() => {
                setToolDraft(null);
                setToolNote(null);
              }}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {toolNote && <p className="section-sub">{toolNote}</p>}

      {draft?.ready && (
        <div className="mission-chat__confirm" role="region" aria-label="Confirm mission">
          <div className="section-label">
            {draft.plan?.phases?.length ? "Confirm & execute plan" : "Confirm mission"}
          </div>
          <ul className="mission-chat__confirm-list">
            <li>
              <strong>Target</strong> <span className="mono">{draft.target}</span>
            </li>
            <li>
              <strong>Posture</strong> {draft.posture}
            </li>
            {draft.nl_goal && (
              <li>
                <strong>Goal</strong> {draft.nl_goal}
              </li>
            )}
            {draft.stealth && (
              <li>
                <strong>Stealth</strong> {draft.stealth}
              </li>
            )}
            {!!draft.plan?.tool_names?.length && (
              <li>
                <strong>Tools</strong>{" "}
                <span className="mono">{draft.plan.tool_names.join(", ")}</span>
              </li>
            )}
            {!!draft.plan?.phases?.length && (
              <li>
                <strong>Phases</strong>{" "}
                {draft.plan.phases
                  .map(
                    (p) =>
                      `${p.name} (${(p.tools || []).map((t) => t.tool).join(", ")})`,
                  )
                  .join(" → ")}
              </li>
            )}
            {!!draft.plan?.new_tools?.length && (
              <li>
                <strong>New tools</strong>{" "}
                {draft.plan.new_tools
                  .map((t) => `${t.name} → ${t.binary}`)
                  .join("; ")}{" "}
                <em>(registered on Launch)</em>
              </li>
            )}
          </ul>
          {draft.plan?.phases?.length ? (
            <p className="section-sub">
              Launch runs this chat plan first (including any new tools), then continues
              with adaptive follow-up phases.
            </p>
          ) : null}
          {launchError && <p className="error-text">{launchError}</p>}
          <div className="mission-chat__confirm-actions">
            <button
              type="button"
              className="btn btn--primary"
              disabled={busy}
              onClick={() => void onLaunch()}
            >
              {draft.plan?.phases?.length ? "Execute plan" : "Launch"}
            </button>
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() => onEditManual?.(draft)}
            >
              Edit in Manual
            </button>
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() => void onDismiss()}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {error && <p className="error-text">{error}</p>}

      <form className="mission-chat__composer" onSubmit={onSubmit}>
        <label className="sr-only" htmlFor="mission-chat-input">
          Message
        </label>
        <textarea
          id="mission-chat-input"
          rows={2}
          placeholder="Ask, plan, or name an authorized target…"
          value={input}
          disabled={busy}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send(input);
            }
          }}
        />
        {streaming ? (
          <button type="button" className="btn btn--danger" onClick={onStop}>
            Stop
          </button>
        ) : (
          <button
            type="submit"
            className="btn btn--primary"
            disabled={busy || !input.trim()}
          >
            Send
          </button>
        )}
      </form>
    </section>
  );
}
