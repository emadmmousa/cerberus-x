import { describe, expect, it } from "vitest";
import { enrichResultForDisplay } from "../lib/enrichResult";

describe("enrichResultForDisplay", () => {
  it("adds partial flags to legacy sqlmap rows with no usable links", () => {
    const enriched = enrichResultForDisplay("sqlmap", {
      tool: "sqlmap",
      vulnerable: false,
      raw_output:
        "[10:31:19] [WARNING] no usable links found (with GET parameters) or forms\n",
    }) as Record<string, unknown>;

    expect(enriched.partial).toBe(true);
    expect(enriched.no_injection_surface).toBe(true);
    expect(String(enriched.note).toLowerCase()).toMatch(/inconclusive/);
  });
});
