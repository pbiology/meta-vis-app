import { describe, expect, it } from "vitest";
import { applyDisplayFilters } from "./taxonFilters";

const entries = [
  { taxon_id: 1, name: "A" },
  { taxon_id: 2, name: "B" },
  { taxon_id: 3, name: "C" },
];

describe("applyDisplayFilters", () => {
  it("returns everything when nothing is filtered", () => {
    const result = applyDisplayFilters(entries, new Set());
    expect(result.visible).toEqual(entries);
    expect(result.hiddenCount).toBe(0);
    expect(result.protectedCount).toBe(0);
  });

  it("hides exact taxon ids and counts them", () => {
    const result = applyDisplayFilters(entries, new Set([1, 3, 99]));
    expect(result.visible.map((e) => e.taxon_id)).toEqual([2]);
    expect(result.hiddenCount).toBe(2);
  });

  it("never hides protected taxa, and reports them", () => {
    const result = applyDisplayFilters(entries, new Set([1, 2]), new Set([2]));
    expect(result.visible.map((e) => e.taxon_id)).toEqual([2, 3]);
    expect(result.hiddenCount).toBe(1);
    expect(result.protectedCount).toBe(1);
  });

  it("does not count protected taxa that are not on a filter list", () => {
    const result = applyDisplayFilters(entries, new Set([1]), new Set([3]));
    expect(result.protectedCount).toBe(0);
  });

  it("keeps the input order", () => {
    const result = applyDisplayFilters([...entries].reverse(), new Set([2]));
    expect(result.visible.map((e) => e.taxon_id)).toEqual([3, 1]);
  });
});
