import { describe, expect, it } from "vitest";
import { buildPageNumbers, formatPageRange } from "../lib/pagination";

describe("pagination", () => {
  it("builds compact page sequences", () => {
    expect(buildPageNumbers(1, 1)).toEqual([1]);
    expect(buildPageNumbers(2, 5)).toEqual([1, 2, 3, 4, 5]);
    expect(buildPageNumbers(5, 10)).toEqual([1, "ellipsis", 4, 5, 6, "ellipsis", 10]);
  });

  it("formats visible ranges", () => {
    expect(formatPageRange(1, 10, 42)).toBe("1–10 of 42");
    expect(formatPageRange(5, 5, 5)).toBe("5 of 5");
    expect(formatPageRange(0, 0, 0)).toBe("No items");
  });
});
