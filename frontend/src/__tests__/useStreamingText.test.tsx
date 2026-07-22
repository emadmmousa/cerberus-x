import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useStreamingText } from "../lib/useStreamingText";

describe("useStreamingText", () => {
  beforeEach(() => {
    // Drive requestAnimationFrame synchronously so we can step the animation.
    let raf = 0;
    vi.stubGlobal(
      "requestAnimationFrame",
      (cb: FrameRequestCallback): number => {
        raf += 1;
        setTimeout(() => cb(performance.now()), 0);
        return raf;
      },
    );
    vi.stubGlobal("cancelAnimationFrame", () => {});
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("reveals buffered text progressively then catches up fully", () => {
    const { result } = renderHook(() => useStreamingText());

    act(() => {
      result.current.push("Hello, operator — planning the recon phase now.");
    });

    // Not fully revealed on the first frame.
    act(() => {
      vi.advanceTimersByTime(0);
    });
    const partial = result.current.text;
    expect(partial.length).toBeGreaterThan(0);

    // After enough frames the whole buffer is shown.
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(result.current.text).toBe(
      "Hello, operator — planning the recon phase now.",
    );
  });

  it("flush reveals everything immediately", () => {
    const { result } = renderHook(() => useStreamingText());
    act(() => {
      result.current.push("chunk one ");
      result.current.push("chunk two");
      result.current.flush();
    });
    expect(result.current.text).toBe("chunk one chunk two");
  });

  it("reset clears the buffer", () => {
    const { result } = renderHook(() => useStreamingText());
    act(() => {
      result.current.push("something");
      result.current.flush();
      result.current.reset();
    });
    expect(result.current.text).toBe("");
  });
});
