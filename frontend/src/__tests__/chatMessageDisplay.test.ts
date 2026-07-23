import { describe, expect, it } from "vitest";
import {
  parseChatMessageContent,
  visibleChatText,
  isPlanningVisible,
  resolveCollapsedVisibleReply,
} from "../lib/chatMessageDisplay";

const THINK_OPEN = String.fromCharCode(60) + "think" + String.fromCharCode(62);
const THINK_CLOSE = String.fromCharCode(60) + "/" + "think" + String.fromCharCode(62);

describe("chatMessageDisplay", () => {
  it("keeps visible prose and folds thinking blocks", () => {
    const raw = [
      "Launch recon on example.com.",
      "",
      THINK_OPEN,
      "hidden chain of thought",
      THINK_CLOSE,
    ].join("\n");

    const parsed = parseChatMessageContent(raw);
    expect(parsed.visible).toBe("Launch recon on example.com.");
    expect(parsed.thinking).toHaveLength(1);
    expect(parsed.thinking[0]).toContain("hidden chain");
    expect(visibleChatText(raw)).toBe("Launch recon on example.com.");
  });

  it("folds firebreak plan blocks out of the visible thread", () => {
    const raw = [
      "Ready when you are.",
      "```firebreak-plan",
      '{"target":"example.com","phases":[]}',
      "```",
    ].join("\n");

    const parsed = parseChatMessageContent(raw);
    expect(parsed.visible).toBe("Ready when you are.");
    expect(parsed.plans).toHaveLength(1);
    expect(parsed.plans[0]).toContain("firebreak-plan");
  });

  it("detects planning prose that should stay collapsed", () => {
    const raw = "### Seed Identification:\n- Email: test@example.com\n\n### Phase Plan:\n";
    expect(isPlanningVisible(raw)).toBe(true);
    expect(isPlanningVisible("OSINT sweep queued — running now.")).toBe(false);
  });

  it("builds a brief confirm alert after folded planning", () => {
    const raw = "### Seed Identification:\n- Email: test@example.com\n\n### Phase Plan:\n";
    expect(
      resolveCollapsedVisibleReply(raw, {
        target: "corp.com",
        needsConfirm: true,
        osintOnly: true,
      }),
    ).toBe("OSINT plan ready for corp.com — confirm below to run intelligence tools.");
  });
});
