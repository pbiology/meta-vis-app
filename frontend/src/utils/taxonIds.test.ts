import { describe, expect, it } from "vitest";
import { parseTaxonIds } from "./taxonIds";

describe("parseTaxonIds", () => {
  it("splits on commas, semicolons, spaces and newlines", () => {
    expect(parseTaxonIds("562, 1392;11676\n4932\t9606 ").ids).toEqual([
      562, 1392, 11676, 4932, 9606,
    ]);
  });

  it("collapses duplicates, keeping first-seen order", () => {
    expect(parseTaxonIds("3,1,3,2,1").ids).toEqual([3, 1, 2]);
  });

  it("reports anything that is not a positive integer", () => {
    const result = parseTaxonIds("562, abc, 0, -5, 12.5, 1e3");
    expect(result.ids).toEqual([562]);
    expect(result.invalid).toEqual(["abc", "0", "-5", "12.5", "1e3"]);
  });

  it("returns nothing for blank input", () => {
    expect(parseTaxonIds("  ,\n ")).toEqual({ ids: [], invalid: [] });
  });
});
