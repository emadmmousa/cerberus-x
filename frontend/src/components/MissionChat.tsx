import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  createMissionChat,
  dismissMissionChatDraft,
  getMissionChat,
  launchMissionChat,
  postMissionChatMessage,
  type ChatMessage,
  type MissionProposal,
} from "../api/client";

type Props = {
  onMissionLaunched?: () => void;
  onEditManual?: (proposal: MissionProposal) => void;
};

export function MissionChat({ onMissionLaunched, onEditManual }: Props) {
  const [chatId, setChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState<MissionProposal | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [launchError, setLaunchError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const ensureChat = useCallback(async () => {
    if (chatId) return chatId;
    const created = await createMissionChat();
    setChatId(created.chat_id);
    return created.chat_id;
  }, [chatId]);

  const refresh = useCallback(async (id: string) => {
    const thread = await getMissionChat(id);
    setMessages(thread.messages ?? []);
    setDraft(thread.draft ?? null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    createMissionChat()
      .then((c) => {
        if (cancelled) return;
        setChatId(c.chat_id);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Failed to start chat");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const el = bottomRef.current;
    if (el && typeof el.scrollIntoView === "function") {
      el.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, draft]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim() || busy) return;
    setBusy(true);
    setError(null);
    setLaunchError(null);
    const text = input.trim();
    setInput("");
    try {
      const id = await ensureChat();
      const res = await postMissionChatMessage(id, text);
      setMessages(res.messages ?? []);
      setDraft(res.draft ?? (res.proposal?.ready ? res.proposal : null));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Send failed");
      setInput(text);
    } finally {
      setBusy(false);
    }
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
      await refresh(chatId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dismiss failed");
    }
  }

  async function onNewChat() {
    setBusy(true);
    setError(null);
    setLaunchError(null);
    try {
      const created = await createMissionChat();
      setChatId(created.chat_id);
      setMessages([]);
      setDraft(null);
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
          <div className="section-label">Mission agent</div>
          <p className="section-sub">
            Describe an authorized mission. Confirm before launch.
          </p>
        </div>
        <button type="button" className="btn" onClick={() => void onNewChat()}>
          New chat
        </button>
      </div>

      <div className="mission-chat__thread" role="log" aria-live="polite">
        {messages.length === 0 && (
          <p className="empty-state">
            Try: “Run a balanced recon on lab.example.com”
          </p>
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
                <Link
                  className="link-btn"
                  to={`/missions/${m.mission_card.task_id}`}
                >
                  Open detail
                </Link>
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {draft?.ready && (
        <div className="mission-chat__confirm" role="region" aria-label="Confirm mission">
          <div className="section-label">Confirm mission</div>
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
          </ul>
          {launchError && <p className="error-text">{launchError}</p>}
          <div className="mission-chat__confirm-actions">
            <button
              type="button"
              className="btn btn--primary"
              disabled={busy}
              onClick={() => void onLaunch()}
            >
              Launch
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

      <form className="mission-chat__composer" onSubmit={(e) => void onSubmit(e)}>
        <label className="sr-only" htmlFor="mission-chat-input">
          Message
        </label>
        <textarea
          id="mission-chat-input"
          rows={2}
          placeholder="Describe the authorized mission…"
          value={input}
          disabled={busy}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void onSubmit(e as unknown as FormEvent);
            }
          }}
        />
        <button
          type="submit"
          className="btn btn--primary"
          disabled={busy || !input.trim()}
        >
          {busy ? "…" : "Send"}
        </button>
      </form>
    </section>
  );
}
