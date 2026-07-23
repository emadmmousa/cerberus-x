import { describe, expect, it } from "vitest";
import {
  buildStrikePromptMessage,
  deckFollowupForProfile,
  strikeProfileMarker,
} from "../lib/strikePromptMessage";
import { AGGRESSIVE_PROMPTS } from "../lib/aggressivePrompts";

describe("strikePromptMessage", () => {
  it("uses profile-specific follow-up for email decks", () => {
    const card = AGGRESSIVE_PROMPTS.find((row) => row.id === "osint-email");
    expect(card).toBeTruthy();
    const message = buildStrikePromptMessage(card!.prompt, card!.targetProfile);
    expect(message).toContain(strikeProfileMarker("email"));
    expect(message).toContain(deckFollowupForProfile("email"));
    expect(message).not.toContain(deckFollowupForProfile("host"));
  });

  it("keeps host decks on hostname follow-up without OSINT marker", () => {
    const card = AGGRESSIVE_PROMPTS.find((row) => row.id === "full-arsenal");
    expect(card).toBeTruthy();
    const message = buildStrikePromptMessage(card!.prompt, card!.targetProfile);
    expect(message).not.toContain("Target profile for this deck:");
    expect(message).toContain(deckFollowupForProfile("host"));
  });

  it("covers all six OSINT target profiles", () => {
    const profiles = ["username", "full_name", "email", "mobile", "social_url", "domain"] as const;
    for (const profile of profiles) {
      expect(strikeProfileMarker(profile)).toContain(profile);
      expect(deckFollowupForProfile(profile)).toMatch(/Wait for my next message/i);
    }
  });
});
