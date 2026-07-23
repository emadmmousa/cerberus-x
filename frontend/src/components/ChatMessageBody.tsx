import { useEffect, useMemo, useRef, useState } from "react";
import {
  type BriefReplyContext,
  isPlanningVisible,
  parseChatMessageContent,
  resolveCollapsedVisibleReply,
} from "../lib/chatMessageDisplay";

type Props = {
  content: string;
  thinkingContent?: string;
  streaming?: boolean;
  /** Keep reasoning/plans in a collapsed "Thinking..." fold (instant chat). */
  collapseThinking?: boolean;
  briefContext?: BriefReplyContext;
};

function foldedThinkingBody(
  parsed: ReturnType<typeof parseChatMessageContent>,
  planningVisible: boolean,
): string {
  const chunks = [...parsed.thinking];
  if (planningVisible && parsed.visible) {
    chunks.unshift(parsed.visible);
  }
  chunks.push(...parsed.plans);
  return chunks.filter(Boolean).join("\n\n");
}

function resolveFoldedBody(
  content: string,
  thinkingContent: string | undefined,
  parsed: ReturnType<typeof parseChatMessageContent>,
  planningVisible: boolean,
  streaming: boolean,
): string {
  if (streaming) return content.trim();
  if (thinkingContent?.trim()) return thinkingContent.trim();
  return foldedThinkingBody(parsed, planningVisible);
}

export function ChatMessageBody({
  content,
  thinkingContent,
  streaming = false,
  collapseThinking = false,
  briefContext,
}: Props) {
  const [thinkingOpen, setThinkingOpen] = useState(false);
  const wasStreaming = useRef(false);

  useEffect(() => {
    if (streaming && !wasStreaming.current) {
      setThinkingOpen(false);
    }
    wasStreaming.current = streaming;
  }, [streaming]);

  const parsed = useMemo(() => parseChatMessageContent(content), [content]);
  const planningVisible = collapseThinking && !streaming && isPlanningVisible(parsed.visible);
  const displayVisible = collapseThinking
    ? streaming
      ? ""
      : resolveCollapsedVisibleReply(content, briefContext)
    : parsed.visible;

  const foldedBody = collapseThinking
    ? resolveFoldedBody(content, thinkingContent, parsed, planningVisible, streaming)
    : "";

  const showThinkingFold = collapseThinking && (streaming || foldedBody.length > 0);

  const thinkingDetails = (
    open: boolean,
    onToggle: (next: boolean) => void,
    body: string,
    live: boolean,
  ) => (
    <details
      open={open}
      className={`agent-fold agent-fold--think${live ? " agent-fold--live" : ""}`}
    >
      <summary
        className="agent-fold__summary"
        onClick={(event) => {
          event.preventDefault();
          onToggle(!open);
        }}
      >
        Thinking...
      </summary>
      {body ? <pre className="agent-fold__body agent-fold__body--stream">{body}</pre> : null}
    </details>
  );

  if (!displayVisible && !showThinkingFold && parsed.thinking.length === 0 && parsed.plans.length === 0) {
    return streaming
      ? thinkingDetails(thinkingOpen, setThinkingOpen, content.trim(), true)
      : null;
  }

  if (collapseThinking) {
    return (
      <>
        {displayVisible ? (
          <div className="mission-chat__content agent-msg__content agent-msg__content--brief">
            {displayVisible}
          </div>
        ) : null}
        {showThinkingFold
          ? thinkingDetails(thinkingOpen, setThinkingOpen, foldedBody, streaming)
          : null}
      </>
    );
  }

  return (
    <>
      {displayVisible ? (
        <div className="mission-chat__content agent-msg__content">{displayVisible}</div>
      ) : streaming ? (
        thinkingDetails(thinkingOpen, setThinkingOpen, content.trim(), true)
      ) : null}

      {parsed.thinking.map((block, index) => (
        <details key={`think-${index}`} className="agent-fold agent-fold--think">
          <summary
            className="agent-fold__summary"
            onClick={(event) => {
              event.preventDefault();
              const node = event.currentTarget.parentElement as HTMLDetailsElement | null;
              if (node) node.open = !node.open;
            }}
          >
            Thinking...
          </summary>
          <pre className="agent-fold__body">{block}</pre>
        </details>
      ))}

      {parsed.plans.map((block, index) => (
        <details key={`plan-${index}`} className="agent-fold agent-fold--plan">
          <summary
            className="agent-fold__summary"
            onClick={(event) => {
              event.preventDefault();
              const node = event.currentTarget.parentElement as HTMLDetailsElement | null;
              if (node) node.open = !node.open;
            }}
          >
            Thinking...
          </summary>
          <pre className="agent-fold__body">{block}</pre>
        </details>
      ))}
    </>
  );
}
