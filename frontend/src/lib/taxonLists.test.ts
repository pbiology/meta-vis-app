import { describe, expect, it } from "vitest";
import type { TaxonListEntry } from "../api/types";
import { entriesById, matchedIds } from "./taxonLists";

function entry(taxon_id: number, merged_ids?: number[]): TaxonListEntry {
  return {
    list_id: "known_pathogens",
    taxon_id,
    taxon_name: `T${taxon_id}`,
    superkingdom: null,
    reason: null,
    min_reads: null,
    added_by: "tester",
    added_at: "2026-09-29",
    updated_by: null,
    updated_at: null,
    merged_ids,
  };
}

describe("entriesById", () => {
  it("finds an entry by its taxon id and by every retired id merged into it", () => {
    const current = entry(28116, [1912894, 1912896]);
    const byId = entriesById([current, entry(562)]);
    expect(byId[28116]).toBe(current);
    expect(byId[1912894]).toBe(current);
    expect(byId[1912896]).toBe(current);
    expect(byId[562].taxon_id).toBe(562);
  });

  it("works for entries without merged ids (add/update responses)", () => {
    expect(Object.keys(entriesById([entry(562)]))).toEqual(["562"]);
  });
});

describe("matchedIds", () => {
  it("includes current and retired ids", () => {
    expect(matchedIds([entry(28116, [1912894])])).toEqual(new Set([28116, 1912894]));
  });
});
