import { beforeEach, describe, expect, it } from "vitest";
import {
  DEFAULT_CHAT_OPTIONS,
  loadChatOptions,
  saveChatOptions,
  toApiOptions,
} from "../lib/chatAgentOptions";

describe("chatAgentOptions auto-run controls", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("defaults Auto Run on and Always Run off", () => {
    expect(DEFAULT_CHAT_OPTIONS.autoRun).toBe(true);
    expect(DEFAULT_CHAT_OPTIONS.alwaysRun).toBe(false);
    const loaded = loadChatOptions();
    expect(loaded.autoRun).toBe(true);
    expect(loaded.alwaysRun).toBe(false);
  });

  it("serializes both flags to the API payload", () => {
    const api = toApiOptions({
      ...DEFAULT_CHAT_OPTIONS,
      autoRun: false,
      alwaysRun: true,
    });
    expect(api.auto_run).toBe(false);
    expect(api.always_run).toBe(true);
  });

  it("round-trips persisted flags", () => {
    saveChatOptions({ ...DEFAULT_CHAT_OPTIONS, autoRun: false, alwaysRun: false });
    const loaded = loadChatOptions();
    expect(loaded.autoRun).toBe(false);
    expect(loaded.alwaysRun).toBe(false);
  });

  it("backfills flags for options saved before the feature existed", () => {
    // Simulate a legacy payload without the new keys.
    localStorage.setItem(
      "firebreak:chatAgentOptions",
      JSON.stringify({ posture: "aggressive", useProxy: true }),
    );
    const loaded = loadChatOptions();
    expect(loaded.autoRun).toBe(true);
    expect(loaded.alwaysRun).toBe(false);
  });
});
