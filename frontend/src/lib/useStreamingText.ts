import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Smooth, fast "typewriter" for streamed LLM output.
 *
 * The local model emits tokens in uneven, bursty chunks, which makes raw
 * `prev + delta` rendering look slow and choppy. Instead we buffer the full
 * target text and reveal it at ~60fps, draining the backlog proportionally so
 * the writing always flows quickly and smoothly, independent of token cadence.
 */
type Options = {
  /** Reveal streamed tokens immediately instead of typewriter animation. */
  instant?: boolean;
};

export function useStreamingText(options: Options = {}) {
  const instant = options.instant ?? false;
  const [text, setText] = useState("");
  const targetRef = useRef("");
  const shownRef = useRef(0);
  const rafRef = useRef<number | null>(null);

  const hasRaf =
    typeof window !== "undefined" &&
    typeof window.requestAnimationFrame === "function";

  const stop = useCallback(() => {
    if (rafRef.current != null && hasRaf) {
      window.cancelAnimationFrame(rafRef.current);
    }
    rafRef.current = null;
  }, [hasRaf]);

  const tick = useCallback(() => {
    const target = targetRef.current;
    const shown = shownRef.current;
    if (shown >= target.length) {
      rafRef.current = null;
      return;
    }
    const remaining = target.length - shown;
    // Reveal a chunk that scales with the backlog: big bursts catch up fast,
    // a trickle still advances a few chars per frame so it keeps moving.
    const step = Math.max(3, Math.ceil(remaining / 6));
    shownRef.current = Math.min(target.length, shown + step);
    setText(target.slice(0, shownRef.current));
    if (hasRaf) {
      rafRef.current = window.requestAnimationFrame(tick);
    }
  }, [hasRaf]);

  const push = useCallback(
    (delta: string) => {
      targetRef.current += delta;
      if (instant || !hasRaf) {
        shownRef.current = targetRef.current.length;
        setText(targetRef.current);
        return;
      }
      if (rafRef.current == null) {
        rafRef.current = window.requestAnimationFrame(tick);
      }
    },
    [hasRaf, instant, tick],
  );

  /** Reveal everything now (stream ended or was stopped). */
  const flush = useCallback(() => {
    stop();
    shownRef.current = targetRef.current.length;
    setText(targetRef.current);
  }, [stop]);

  /** Clear all state before a new turn. */
  const reset = useCallback(() => {
    stop();
    targetRef.current = "";
    shownRef.current = 0;
    setText("");
  }, [stop]);

  useEffect(() => stop, [stop]);

  return { text, push, flush, reset };
}
