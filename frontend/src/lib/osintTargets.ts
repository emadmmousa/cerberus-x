import { ensureUtf8Text } from "./textEncoding";

export type OsintTargetKind =
  | "social_url"
  | "username"
  | "full_name"
  | "mobile"
  | "email"
  | "domain";

export type OsintSeed = {
  kind: OsintTargetKind;
  value: string;
  display?: string;
};

export const OSINT_TARGET_KINDS: Array<{ id: OsintTargetKind; label: string; placeholder: string }> = [
  { id: "social_url", label: "Social profile URL", placeholder: "https://instagram.com/handle" },
  { id: "username", label: "Username", placeholder: "@handle or jsmith" },
  { id: "full_name", label: "Full name", placeholder: "Jane Doe" },
  { id: "mobile", label: "Mobile number", placeholder: "+1 555 0100" },
  { id: "email", label: "Email", placeholder: "person@company.com" },
  { id: "domain", label: "Domain", placeholder: "company.com" },
];

export function osintKindLabel(kind: OsintTargetKind | string): string {
  return OSINT_TARGET_KINDS.find((row) => row.id === kind)?.label ?? kind;
}

export function osintSeedLabel(seed: OsintSeed): string {
  return seed.display?.trim() || seed.value.trim();
}

export function validateOsintSeed(kind: OsintTargetKind, value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return "Value is required";
  if (kind === "email" && !/^[\w.+-]+@[\w.-]+\.\w+$/.test(trimmed)) {
    return "Enter a valid email address";
  }
  if (kind === "mobile" && trimmed.replace(/\D/g, "").length < 7) {
    return "Enter a valid mobile number";
  }
  if (kind === "domain" && !/^(?:https?:\/\/)?(?:[\w-]+\.)+[\w-]{2,}/.test(trimmed)) {
    return "Enter a valid domain or URL";
  }
  if (kind === "social_url" && !/^https?:\/\//.test(trimmed) && !/[\w-]+\.[\w.-]+/.test(trimmed)) {
    return "Enter a social profile URL";
  }
  if (kind === "username" && trimmed.replace(/^@/, "").length < 2) {
    return "Enter a username";
  }
  if (kind === "full_name" && trimmed.length < 2) {
    return "Enter a full name";
  }
  return null;
}

export function normalizeOsintSeed(kind: OsintTargetKind, value: string): OsintSeed {
  const trimmed = value.trim();
  if (kind === "email") {
    const v = trimmed.toLowerCase();
    return { kind, value: v, display: v };
  }
  if (kind === "username") {
    const v = trimmed.replace(/^@/, "").toLowerCase();
    return { kind, value: v, display: `@${v}` };
  }
  if (kind === "mobile") {
    const digits = trimmed.replace(/\D/g, "");
    const v = trimmed.startsWith("+") ? `+${digits}` : digits;
    return { kind, value: v, display: v };
  }
  if (kind === "domain") {
    const probe = trimmed.includes("://") ? trimmed : `https://${trimmed}`;
    try {
      const host = new URL(probe).hostname.replace(/^www\./, "");
      return { kind, value: host, display: host };
    } catch {
      return { kind, value: trimmed, display: trimmed };
    }
  }
  if (kind === "social_url") {
    const probe = trimmed.includes("://") ? trimmed : `https://${trimmed}`;
    return { kind, value: probe.replace(/\/$/, ""), display: probe.replace(/\/$/, "") };
  }
  const v = trimmed.replace(/\s+/g, " ");
  return { kind, value: ensureUtf8Text(v), display: ensureUtf8Text(v) };
}

export function mergeOsintSeeds(existing: OsintSeed[], next: OsintSeed): OsintSeed[] {
  const key = `${next.kind}:${next.value}`;
  const filtered = existing.filter((seed) => `${seed.kind}:${seed.value}` !== key);
  return [...filtered, next];
}
