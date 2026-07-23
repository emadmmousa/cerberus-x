import { FormEvent, forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  createMissionChat,
  dismissMissionChatDraft,
  getChatAgentConfig,
  getMissionChat,
  launchMissionChat,
  postMissionChatMessage,
  registerCustomTool,
  streamMissionChatMessage,
  type ChatAgentConfig,
  type ChatMessage,
  type CustomToolDraft,
  type MissionProposal,
} from "../api/client";
import { useStreamingText } from "../lib/useStreamingText";
import {
  loadChatOptions,
  toApiOptions,
  type ChatAgentOptions,
} from "../lib/chatAgentOptions";
import { AGENT_QUICK_PROMPTS } from "../lib/agentQuickPrompts";
import { buildStrikePromptMessage } from "../lib/strikePromptMessage";
import { briefContextForChatMessage } from "../lib/chatBriefContext";
import type { OsintSeed } from "../lib/osintTargets";
import { AggressivePromptDeck } from "./AggressivePromptDeck";
import { ChatAgentToolbar } from "./ChatAgentToolbar";
import { ChatMessageBody } from "./ChatMessageBody";
import { OsintTargetPanel } from "./OsintTargetPanel";

const ACTIVE_CHAT_STORAGE_KEY = "firebreak:activeChatId";

type Props = {
  onMissionLaunched?: () => void;
  onEditManual?: (proposal: MissionProposal) => void;
  compact?: boolean;
  chromeless?: boolean;
  showLibrary?: boolean;
  onShowLibraryChange?: (open: boolean) => void;
  osintSeeds?: OsintSeed[];
  onOsintSeedsChange?: (seeds: OsintSeed[]) => void;
  showOsintPanel?: boolean;
  instantChat?: boolean;
};

export type MissionChatHandle = {
  newChat: () => Promise<void>;
  sendPrompt: (text: string) => Promise<void>;
};

export const MissionChat = forwardRef<MissionChatHandle, Props>(function MissionChat(
  {
    onMissionLaunched,
    onEditManual,
    compact = false,
    chromeless = false,
    showLibrary: showLibraryProp,
    onShowLibraryChange,
    osintSeeds: osintSeedsProp,
    onOsintSeedsChange,
    showOsintPanel = true,
    instantChat = false,
  },
  ref,
) {
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
  } = useStreamingText({ instant: instantChat });
  const [error, setError] = useState<string | null>(null);
  const [launchError, setLaunchError] = useState<string | null>(null);
  const [lastMissionLaunched, setLastMissionLaunched] = useState(false);
  const [showLibraryInternal, setShowLibraryInternal] = useState(false);
  const showLibrary = showLibraryProp ?? showLibraryInternal;
  const setShowLibrary = onShowLibraryChange ?? setShowLibraryInternal;

  function toggleLibrary() {
    setShowLibrary(!showLibrary);
  }
  const [agentConfig, setAgentConfig] = useState<ChatAgentConfig | null>(null);
  const [agentOptions, setAgentOptions] = useState<ChatAgentOptions>(() => loadChatOptions());
  const [remoteProcessing, setRemoteProcessing] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const thinkingArchiveRef = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    if (osintSeedsProp === undefined) return;
    setAgentOptions((prev) =>
      prev.osintSeeds === osintSeedsProp ? prev : { ...prev, osintSeeds: osintSeedsProp },
    );
  }, [osintSeedsProp]);

  const ensureChat = useCallback(async () => {
    if (chatId) return chatId;
    const created = await createMissionChat();
    setChatId(created.chat_id);
    return created.chat_id;
  }, [chatId]);

  useEffect(() => {
    let cancelled = false;
    getChatAgentConfig()
      .then((cfg) => {
        if (cancelled) return;
        setAgentConfig(cfg);
        setAgentOptions((prev) => ({
          ...prev,
          model: prev.model || cfg.default_model,
          posture: prev.posture || (cfg.defaults.posture as ChatAgentOptions["posture"]),
        }));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

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
            const processing = !!thread.processing;
            setRemoteProcessing(processing);
            setStreaming(processing);
            setBusy(processing);
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
    if (!chatId || !remoteProcessing) return;
    let cancelled = false;
    let timer: number | undefined;

    const poll = async () => {
      try {
        const thread = await getMissionChat(chatId);
        if (cancelled) return;
        setMessages(thread.messages ?? []);
        setDraft(thread.draft ?? null);
        if (thread.processing) {
          setStreaming(true);
          setBusy(true);
          setRemoteProcessing(true);
          timer = window.setTimeout(poll, 1500);
        } else {
          setStreaming(false);
          setBusy(false);
          setRemoteProcessing(false);
        }
      } catch {
        if (!cancelled) {
          timer = window.setTimeout(poll, 2500);
        }
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [chatId, remoteProcessing]);

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
      if (!clean || busy || remoteProcessing) return;
      const apiOptions = toApiOptions(agentOptions);
      setBusy(true);
      setError(null);
      setLaunchError(null);
      setLastMissionLaunched(false);
      setInput("");
      // Optimistic user bubble + live assistant bubble.
      setMessages((prev) => [...prev, { role: "user", content: clean, ts: Date.now() }]);
      setShowLibrary(false);
      resetLive();
      setStreaming(true);
      setRemoteProcessing(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const id = await ensureChat();
        await streamMissionChatMessage(
          id,
          clean,
          {
            signal: controller.signal,
            onDelta: (delta) => pushLive(delta),
            onDone: (payload) => {
              const archived = liveText.trim();
              setMessages(payload.messages ?? []);
              if (payload.mission_launched) {
                setDraft(null);
                setToolDraft(null);
                setLastMissionLaunched(true);
                onMissionLaunched?.();
              } else {
                setLastMissionLaunched(false);
                setDraft(payload.draft ?? (payload.proposal?.ready ? payload.proposal : null));
                if (payload.toolProposal && !payload.proposal?.auto_execute) {
                  setToolDraft(payload.toolProposal);
                  setToolNote(null);
                }
              }
              if (archived) {
                const source = [...(payload.messages ?? [])]
                  .reverse()
                  .find((row) => row.role === "assistant" && !row.mission_card && !row.thinking_content);
                if (source?.ts != null) {
                  thinkingArchiveRef.current.set(String(source.ts), archived);
                }
              }
              if (payload.launch_error) {
                setLaunchError(payload.launch_error);
              }
              resetLive();
              setAgentOptions((prev) => ({ ...prev, attachments: [] }));
            },
            onError: (msg) => setError(msg),
          },
          apiOptions,
        );
      } catch (err) {
        if (controller.signal.aborted) {
          // User stopped the stream — keep whatever streamed and persist via
          // the non-streaming endpoint so the thread stays consistent.
          resetLive();
        } else {
          // Transport failure: fall back to the non-streaming endpoint.
          try {
            const id = await ensureChat();
            const res = await postMissionChatMessage(id, clean, apiOptions);
            setMessages(res.messages ?? []);
            if (res.mission_launched) {
              setDraft(null);
              setToolDraft(null);
              setLastMissionLaunched(true);
              onMissionLaunched?.();
            } else {
              setLastMissionLaunched(false);
              setDraft(res.draft ?? (res.proposal?.ready ? res.proposal : null));
            }
            if (res.launch_error) {
              setLaunchError(res.launch_error);
            }
            setAgentOptions((prev) => ({ ...prev, attachments: [] }));
          } catch (e2) {
            setError(e2 instanceof Error ? e2.message : "Send failed");
            setInput(clean);
          }
          resetLive();
        }
      } finally {
        setStreaming(false);
        setBusy(false);
        setRemoteProcessing(false);
        abortRef.current = null;
      }
    },
    [agentOptions, busy, ensureChat, instantChat, onMissionLaunched, pushLive, remoteProcessing, resetLive],
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
        use_proxy: agentOptions.useProxy,
        proxy_protocol: agentOptions.proxyProtocol,
        osint_seeds: agentOptions.osintSeeds.map((seed) => ({
          kind: seed.kind,
          value: seed.value,
          display: seed.display,
        })),
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
    if (!chromeless) setShowLibrary(true);
  }

  useImperativeHandle(ref, () => ({ newChat: onNewChat, sendPrompt: send }), [onNewChat, send]);

  const lastAssistantIndex = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i]?.role === "assistant") return i;
    }
    return -1;
  }, [messages]);

  const agentStatus = streaming || remoteProcessing ? "stream" : busy ? "busy" : "ready";
  const agentStatusLabel = streaming || remoteProcessing
    ? remoteProcessing && !liveText
      ? "Thinking"
      : "Streaming"
    : busy
      ? "Working"
      : agentConfig?.llm_reachable === false
        ? "LLM offline"
        : "Ready";

  return (
    <section
      className={`panel mission-chat agent-shell${compact ? " agent-shell--compact" : ""}${chromeless ? " agent-shell--chromeless" : ""}${instantChat ? " agent-shell--instant" : ""}`}
      aria-label="Mission chat"
    >
      {!chromeless && (
      <header className={`agent-hero${compact ? " agent-hero--compact" : ""}`}>
        {compact ? (
          <>
            <div className="agent-hero__inline">
              <div className={`agent-status agent-status--${agentStatus}`}>
                <span className="agent-status__dot" aria-hidden="true" />
                {agentStatusLabel}
              </div>
              <span className="agent-hero__hint">Authorized targets only</span>
            </div>
            <div className="agent-hero__actions">
              <button
                type="button"
                className="btn btn--ghost btn--sm mission-chat__library-toggle"
                disabled={busy}
                onClick={toggleLibrary}
              >
                {showLibrary ? "Hide library" : "Strike library"}
              </button>
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => void onNewChat()}>
                New chat
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="agent-hero__brand">
              <div className="agent-hero__glyph" aria-hidden="true">
                FB
              </div>
              <div>
                <h2 className="agent-hero__title">Firebreak Agent</h2>
                <p className="agent-hero__tagline">
                  Plan strikes, invent methods, launch missions — authorized targets only.
                </p>
                <div className={`agent-status agent-status--${agentStatus}`}>
                  <span className="agent-status__dot" aria-hidden="true" />
                  {agentStatusLabel}
                </div>
              </div>
            </div>
            <div className="agent-hero__actions">
              <button
                type="button"
                className="btn mission-chat__library-toggle"
                disabled={busy}
                onClick={toggleLibrary}
              >
                {showLibrary ? "Hide library" : "Strike library"}
              </button>
              <button type="button" className="btn" onClick={() => void onNewChat()}>
                New chat
              </button>
            </div>
          </>
        )}
      </header>
      )}

      <div className="agent-body">
        {showLibrary && (
          <AggressivePromptDeck
            disabled={busy}
            onSelect={(card) =>
              void send(buildStrikePromptMessage(card.prompt, card.targetProfile))
            }
          />
        )}

        {!showLibrary && messages.length === 0 && !liveText && (
          <div className={`agent-welcome${compact || chromeless ? " agent-welcome--compact" : ""}`}>
            {chromeless ? (
              <>
                <p className="agent-welcome__lead">
                  Ask anything about an authorized target — recon, exploits, hardening, or mission plans.
                </p>
                <div className="agent-welcome__chips">
                  {[
                    "Map subdomains and live hosts for my authorized domain",
                    "Design an aggressive recon → vuln chain",
                    "Explain WAF bypass options for a reflected XSS",
                    "Plan OSINT-only leak hunting for an email seed",
                  ].map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      className="agent-chip agent-chip--creative"
                      disabled={busy}
                      onClick={() => void send(prompt)}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <>
                <p className="agent-welcome__lead">
                  Quick orders — pick a playbook, then send your authorized target in the next message.
                </p>
                <div className="agent-welcome__chips">
                  {AGENT_QUICK_PROMPTS.map((item) => (
                    <button
                      key={item.label}
                      type="button"
                      className="agent-chip"
                      disabled={busy}
                      onClick={() => void send(buildStrikePromptMessage(item.prompt))}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        <div
          className={`agent-thread mission-chat__thread${messages.length === 0 && !liveText ? " agent-thread--empty" : ""}`}
          role="log"
          aria-live="polite"
        >
          {messages.map((m, i) => (
            <div
              key={`${m.ts ?? i}-${m.role}`}
              className={`agent-msg${m.role === "user" ? " agent-msg--user" : " agent-msg--assistant"}`}
            >
              <div className="agent-msg__avatar" aria-hidden="true">
                {m.role === "user" ? "You" : "AI"}
              </div>
              <div className="agent-msg__bubble">
                <div className="agent-msg__label">
                  {m.role === "user" ? "Operator" : "Agent"}
                </div>
                {m.role === "user" ? (
                  <div className="mission-chat__content agent-msg__content">{m.content}</div>
                ) : (
                  <ChatMessageBody
                    content={m.content}
                    thinkingContent={
                      m.thinking_content ||
                      (m.ts != null ? thinkingArchiveRef.current.get(String(m.ts)) : undefined)
                    }
                    collapseThinking={instantChat}
                    briefContext={
                      instantChat
                        ? briefContextForChatMessage(m, {
                            isLatestAssistant: i === lastAssistantIndex,
                            draft,
                            hasToolDraft: !!toolDraft,
                            launchError,
                            missionLaunched: i === lastAssistantIndex && lastMissionLaunched,
                          })
                        : undefined
                    }
                  />
                )}
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
            </div>
          ))}

          {streaming && (
            <div className="agent-msg agent-msg--assistant agent-msg--streaming">
              <div className="agent-msg__avatar" aria-hidden="true">
                AI
              </div>
              <div className="agent-msg__bubble">
                <div className="agent-msg__label">Agent</div>
                {liveText ? (
                  <ChatMessageBody content={liveText} streaming collapseThinking={instantChat} />
                ) : (
                  <p className="agent-msg__thinking" aria-live="polite">
                    Thinking…
                  </p>
                )}
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {toolDraft && (
          <details open className="agent-fold agent-fold--card">
            <summary className="agent-fold__summary">
              New tool proposal · <span className="mono">{toolDraft.name}</span>
            </summary>
            <div
              className="agent-card mission-chat__confirm agent-fold__panel"
              role="region"
              aria-label="Approve custom tool"
            >
            <div className="agent-card__head">
              <h3 className="agent-card__title">New tool proposal</h3>
              <span className="badge">{toolDraft.risk ?? "medium"} risk</span>
            </div>
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
          </details>
        )}

        {toolNote && <p className="section-sub">{toolNote}</p>}

        {draft?.ready && !draft.auto_execute && (
          <details open className="agent-fold agent-fold--card agent-fold--confirm">
            <summary className="agent-fold__summary">
              {draft.plan?.phases?.length ? "Confirm plan" : "Confirm mission"} ·{" "}
              <span className="mono">{draft.target}</span> · {draft.posture}
            </summary>
            <div
              className="agent-card mission-chat__confirm agent-fold__panel"
              role="region"
              aria-label="Confirm mission"
            >
            <div className="agent-card__head">
              <h3 className="agent-card__title">
                {draft.plan?.phases?.length ? "Confirm & execute plan" : "Confirm mission"}
              </h3>
              <span className="badge badge--ok">{draft.posture}</span>
            </div>
            <ul className="mission-chat__confirm-list">
              <li>
                <strong>Target</strong> <span className="mono">{draft.target}</span>
              </li>
              {!!draft.osint_seeds?.length && (
                <li>
                  <strong>OSINT seeds</strong>{" "}
                  <span className="mono">
                    {(draft.osint_seeds as Array<{ display?: string; value?: string }>)
                      .map((seed) => seed.display || seed.value)
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </li>
              )}
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
            </ul>
            {!!draft.plan?.phases?.length && (
              <div className="agent-phase-pills">
                {draft.plan.phases.map((p) => (
                  <span key={p.name} className="agent-phase-pill">
                    {p.name}
                  </span>
                ))}
              </div>
            )}
            {draft.plan?.phases?.length ? (
              <p className="section-sub">
                Launch runs this chat plan first (including any new tools), then continues
                with adaptive follow-up phases.
              </p>
            ) : null}
            {launchError && <p className="error-text">{launchError}</p>}
            {launchError && /authorized/i.test(launchError) && (
              <button
                type="button"
                className="btn btn--ghost"
                disabled={busy}
                onClick={() => void send("add to authorized list")}
              >
                Authorize target &amp; retry
              </button>
            )}
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
          </details>
        )}

        {error && <p className="error-text">{error}</p>}

        {showOsintPanel && (
          <OsintTargetPanel
            seeds={agentOptions.osintSeeds}
            disabled={busy}
            onChange={(osintSeeds) => {
              setAgentOptions((prev) => ({ ...prev, osintSeeds }));
              onOsintSeedsChange?.(osintSeeds);
            }}
          />
        )}

        <form className="agent-dock mission-chat__composer" onSubmit={onSubmit}>
          <div className="agent-dock__surface mission-chat__composer-box">
            <ChatAgentToolbar
              config={agentConfig}
              options={agentOptions}
              disabled={busy}
              hideDeepThink={instantChat}
              onChange={setAgentOptions}
            />
            <div className="agent-dock__row mission-chat__composer-row">
              <label className="sr-only" htmlFor="mission-chat-input">
                Message
              </label>
              <textarea
                id="mission-chat-input"
                className="agent-dock__input"
                rows={2}
                placeholder={
                  instantChat
                    ? "Message the agent… (Enter to send, Shift+Enter for newline)"
                    : "Ask, plan, or name an authorized target… (Enter to send)"
                }
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
                <button
                  type="button"
                  className="btn btn--danger agent-send agent-send--stop"
                  onClick={onStop}
                >
                  Stop
                </button>
              ) : (
                <button
                  type="submit"
                  className="btn btn--primary agent-send"
                  disabled={busy || !input.trim()}
                >
                  Send
                </button>
              )}
            </div>
          </div>
        </form>
      </div>
    </section>
  );
});
