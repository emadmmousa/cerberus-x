import { describe, expect, it } from "vitest";
import { ensureUtf8Text, repairMojibake } from "../lib/textEncoding";

describe("textEncoding", () => {
  it("repairs Arabic UTF-8 mojibake", () => {
    const arabic = "عبد الباسط هارون جبريل";
    const bytes = new TextEncoder().encode(arabic);
    const mojibake = [...bytes].map((b) => String.fromCharCode(b)).join("");
    expect(repairMojibake(mojibake)).toBe(arabic);
    expect(ensureUtf8Text(mojibake)).toBe(arabic);
  });
});
