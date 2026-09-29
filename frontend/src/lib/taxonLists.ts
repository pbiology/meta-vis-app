import type { TaxonListEntry } from "../api/types";

/** IDs of the system taxon lists seeded by the backend (app/taxon_lists/kinds.py). */
export const TAXON_LIST_IDS = {
  outbreakIgnorelist: "outbreak_ignorelist",
  knownPathogens: "known_pathogens",
  ntcIgnorelist: "ntc_ignorelist",
  ntcKnownContaminants: "ntc_known_contaminants",
} as const;

export type SystemTaxonListId = (typeof TAXON_LIST_IDS)[keyof typeof TAXON_LIST_IDS];

/**
 * Look entries up by any id they match: their taxon id and every retired
 * NCBI id merged into it. A sample classified with an older database reports
 * the retired id; matching only `taxon_id` would miss it.
 */
export function entriesById(entries: TaxonListEntry[]): Record<number, TaxonListEntry> {
  const byId: Record<number, TaxonListEntry> = {};
  for (const entry of entries) {
    byId[entry.taxon_id] = entry;
    for (const id of entry.merged_ids ?? []) byId[id] ??= entry;
  }
  return byId;
}

/** Every id the entries match — see entriesById. */
export function matchedIds(entries: TaxonListEntry[]): Set<number> {
  return new Set(Object.keys(entriesById(entries)).map(Number));
}
