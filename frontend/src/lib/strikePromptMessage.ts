import type { TargetProfile } from "./aggressivePrompts";
import { TARGET_PROFILE_CATEGORIES } from "./aggressivePrompts";
import { type OsintSeed } from "./osintTargets";

const TARGET_KIND_ORDER: OsintSeed["kind"][] = [
  "full_name",
  "email",
  "username",
  "mobile",
  "domain",
  "social_url",
];

/** Marker parsed by chat intake to prefer a seed kind on the follow-up message. */
export function strikeProfileMarker(targetProfile: TargetProfile): string | null {
  if (targetProfile === "host") return null;
  return `Target profile for this deck: ${targetProfile} (OSINT-only).`;
}

const FOLLOWUP_BY_PROFILE: Record<TargetProfile, string> = {
  host:
    "Wait for my next message with the authorized hostname or URL before launching or emitting a firebreak-plan.",
  username:
    "Wait for my next message with the authorized username or @handle before launching or emitting a firebreak-plan.",
  full_name:
    "Wait for my next message with the authorized full name before launching or emitting a firebreak-plan.",
  email:
    "Wait for my next message with the authorized email address before launching or emitting a firebreak-plan.",
  mobile:
    "Wait for my next message with the authorized phone number before launching or emitting a firebreak-plan.",
  social_url:
    "Wait for my next message with the authorized social profile URL before launching or emitting a firebreak-plan.",
  domain:
    "Wait for my next message with the authorized domain name before launching or emitting a firebreak-plan.",
};

/** Legacy generic follow-up (host + any seed). */
export const DECK_TARGET_FOLLOWUP = FOLLOWUP_BY_PROFILE.host;

export function deckFollowupForProfile(targetProfile: TargetProfile = "host"): string {
  return FOLLOWUP_BY_PROFILE[targetProfile] ?? FOLLOWUP_BY_PROFILE.host;
}

export function primaryOsintTarget(seeds: OsintSeed[]): string {
  for (const kind of TARGET_KIND_ORDER) {
    const hit = seeds.find((seed) => seed.kind === kind);
    if (hit) return hit.display?.trim() || hit.value.trim();
  }
  const first = seeds[0];
  return first ? first.display?.trim() || first.value.trim() : "";
}

/** Build the chat message sent when an operator picks a Strike library card. */
export function buildStrikePromptMessage(
  prompt: string,
  targetProfile: TargetProfile = "host",
): string {
  const parts = [prompt.trim()];
  const marker = strikeProfileMarker(targetProfile);
  if (marker) parts.push(marker);
  parts.push(deckFollowupForProfile(targetProfile));
  return parts.join("\n\n");
}

export function targetProfilePlaceholder(targetProfile: TargetProfile): string {
  if (targetProfile === "host") return "hostname or URL";
  return (
    TARGET_PROFILE_CATEGORIES.find((row) => row.id === targetProfile)?.label.toLowerCase() ??
    targetProfile
  );
}
