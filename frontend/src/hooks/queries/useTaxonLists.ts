import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import {
  addTaxonListEntry,
  getTaxonListEntries,
  getTaxonLists,
  removeTaxonListEntry,
  updateTaxonListEntry,
  type NewTaxonListEntry,
  type TaxonListEntryChanges,
} from "../../api/taxonLists";
import type { TaxonListKind } from "../../api/types";
import { TAXON_LIST_IDS } from "../../lib/taxonLists";
import { alertKeys } from "./useAlerts";
import { caseKeys } from "./useCases";
import { ntcKeys } from "./useNtc";

export const taxonListKeys = {
  all: ["taxonLists"] as const,
  lists: (kind: TaxonListKind | null = null) => ["taxonLists", "lists", kind] as const,
  entries: (listId: string) => ["taxonLists", listId, "entries"] as const,
  filteredEntries: (listId: string, superkingdom: string | null) =>
    ["taxonLists", listId, "entries", superkingdom] as const,
};

// Queries whose results are computed from a list, refreshed when it changes.
const DEPENDENT_KEYS: Record<string, readonly (readonly unknown[])[]> = {
  [TAXON_LIST_IDS.outbreakIgnorelist]: [alertKeys.all],
  [TAXON_LIST_IDS.knownPathogens]: [caseKeys.pathogenCases()],
  [TAXON_LIST_IDS.ntcIgnorelist]: [ntcKeys.all],
  [TAXON_LIST_IDS.ntcKnownContaminants]: [ntcKeys.all],
};

function invalidateList(qc: QueryClient, listId: string) {
  return Promise.all(
    [taxonListKeys.entries(listId), ...(DEPENDENT_KEYS[listId] ?? [])].map((queryKey) =>
      qc.invalidateQueries({ queryKey })
    )
  );
}

export function useTaxonLists(kind: TaxonListKind | null = null) {
  return useQuery({
    queryKey: taxonListKeys.lists(kind),
    queryFn: () => getTaxonLists(kind),
  });
}

export function useTaxonListEntries(listId: string, superkingdom: string | null = null) {
  return useQuery({
    queryKey: taxonListKeys.filteredEntries(listId, superkingdom),
    queryFn: () => getTaxonListEntries(listId, superkingdom),
  });
}

export function useAddTaxonListEntry(listId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entry: NewTaxonListEntry) => addTaxonListEntry(listId, entry),
    onSuccess: () => invalidateList(qc, listId),
  });
}

export function useUpdateTaxonListEntry(listId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taxonId, changes }: { taxonId: number; changes: TaxonListEntryChanges }) =>
      updateTaxonListEntry(listId, taxonId, changes),
    onSuccess: () => invalidateList(qc, listId),
  });
}

export function useRemoveTaxonListEntry(listId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taxonId: number) => removeTaxonListEntry(listId, taxonId),
    onSuccess: () => invalidateList(qc, listId),
  });
}
