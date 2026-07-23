/** Repair UTF-8 text that was mis-decoded as Latin-1 (e.g. Arabic mojibake). */

const MOJIBAKE_RE = /[ØÙÃâ�]/;

function textQuality(text: string): number {
  const bad = (text.match(MOJIBAKE_RE)?.length ?? 0) + (text.match(/[\u0080-\u009f]/g)?.length ?? 0);
  const letters = [...text].filter((ch) => /\p{L}/u.test(ch) && ch.charCodeAt(0) > 127).length;
  return letters * 10 - bad * 100;
}

export function looksMojibake(text: string): boolean {
  return !!text && (MOJIBAKE_RE.test(text) || /[\u0080-\u009f]/.test(text));
}

export function repairMojibake(text: string): string {
  if (!text || !looksMojibake(text)) return text;
  try {
    const bytes = Uint8Array.from([...text].map((ch) => ch.charCodeAt(0) & 0xff));
    const repaired = new TextDecoder("utf-8").decode(bytes);
    return textQuality(repaired) > textQuality(text) ? repaired : text;
  } catch {
    return text;
  }
}

export function ensureUtf8Text(text: string): string {
  return repairMojibake(text ?? "");
}
