/** IDs of the system taxon lists seeded by the backend (app/taxon_lists/kinds.py). */
export const TAXON_LIST_IDS = {
  outbreakIgnorelist: "outbreak_ignorelist",
  knownPathogens: "known_pathogens",
  ntcIgnorelist: "ntc_ignorelist",
  ntcKnownContaminants: "ntc_known_contaminants",
} as const;

export type SystemTaxonListId = (typeof TAXON_LIST_IDS)[keyof typeof TAXON_LIST_IDS];
