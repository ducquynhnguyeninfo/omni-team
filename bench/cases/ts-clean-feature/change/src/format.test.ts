import { describe, expect, it } from "vitest";
import { formatPercent } from "./format";

describe("formatPercent", () => {
  it("formats ratios as percentages", () => {
    expect(formatPercent(0.1234)).toBe("12.3%");
    expect(formatPercent(1, 0)).toBe("100%");
  });

  it("rejects non-finite input", () => {
    expect(() => formatPercent(Number.NaN)).toThrow(RangeError);
  });
});
