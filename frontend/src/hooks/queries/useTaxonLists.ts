import {
  keepPreviousData,
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import {
  addTaxonListEntry,
  bulkAddTaxonListEntries,
  createTaxonList,
  deleteTaxonList,
  getAllTaxonListEntries,
  getTaxonListEntryPage,
  getTaxonListTaxonIds,
  getTaxonLists,
  removeTaxonListEntry,
  updateTaxonList,
  updateTaxonListEntry,
  type BulkAddTaxonListEntries,
  type EntryPageParams,
  type NewTaxonList,
  type NewTaxonListEntry,
  type TaxonListChanges,
  type TaxonListEntryChanges,
} from "../../api/taxonLists";
import type { TaxonListKind } from "../../api/types";
import { TAXON_LIST_IDS } from "../../lib/taxonLists";
import { alertKeys } from "./useAlerts";
import { caseKeys } from "./useCases";
import { ntcKeys } from "./useNtc";

export const taxonListKeys = {
  all: ["taxonLists"] as const,
  lists: (kind?: TaxonListKind) =>
    kind ? (["taxonLists", "lists", kind] as const) : (["taxonLists", "lists"] as const),
  entries: (listId: string) => ["taxonLists", listId, "entries"] as const,
  // All below share the entries(listId) prefix, so one invalidation refreshes them.
  allEntries: (listId: string, superkingdom: string | null) =>
    ["taxonLists", listId, "entries", "all", superkingdom] as const,
  entryPage: (listId: string, params: EntryPageParams) =>
    ["taxonLists", listId, "entries", "page", params] as const,
  taxonIds: (listId: string) => ["taxonLists", listId, "entries", "ids"] as const,
};

// Queries whose results are computed from a list, refreshed when it changes.
const DEPENDENT_KEYS: Record<string, readonly (readonly unknown[])[]> = {
  [TAXON_LIST_IDS.outbreakIgnorelist]: [alertKeys.all],
  [TAXON_LIST_IDS.knownPathogens]: [caseKeys.pathogenCases()],
  [TAXON_LIST_IDS.ntcIgnorelist]: [ntcKeys.all],
  [TAXON_LIST_IDS.ntcKnownContaminants]: [ntcKeys.all],
};

function invalidateList(qc: QueryClient, listId: string) {
  // The overview carries entry counts, so it changes with the entries too.
  return Promise.all(
    [taxonListKeys.entries(listId), taxonListKeys.lists(), ...(DEPENDENT_KEYS[listId] ?? [])].map(
      (queryKey) => qc.invalidateQueries({ queryKey })
    )
  );
}

export function useTaxonLists(kind?: TaxonListKind) {
  return useQuery({
    queryKey: taxonListKeys.lists(kind),
    queryFn: () => getTaxonLists(kind ?? null),
  });
}

export interface DisplayFilterIds {
  /** Union of taxon ids on the given lists; empty until every list has loaded. */
  hiddenIds: Set<number>;
  isLoading: boolean;
  isError: boolean;
}

/**
 * The taxa hidden by a user's active display filters.
 *
 * All-or-nothing: while any list is loading or has failed, nothing is hidden,
 * so the table never filters on a partial set and silently shows less than
 * the user chose — or more than it claims.
 */
export function useDisplayFilterIds(listIds: string[]): DisplayFilterIds {
  return useQueries({
    queries: listIds.map((listId) => ({
      queryKey: taxonListKeys.taxonIds(listId),
      queryFn: () => getTaxonListTaxonIds(listId),
    })),
    combine: (results) => {
      const isLoading = results.some((r) => r.isLoading);
      const isError = results.some((r) => r.isError);
      const hiddenIds = new Set<number>();
      if (!isLoading && !isError) {
        for (const r of results) for (const id of r.data ?? []) hiddenIds.add(id);
      }
      return { hiddenIds, isLoading, isError };
    },
  });
}

export function useCreateTaxonList() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (list: NewTaxonList) => createTaxonList(list),
    onSuccess: () => qc.invalidateQueries({ queryKey: taxonListKeys.lists() }),
  });
}

export function useUpdateTaxonList() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ listId, changes }: { listId: string; changes: TaxonListChanges }) =>
      updateTaxonList(listId, changes),
    onSuccess: () => qc.invalidateQueries({ queryKey: taxonListKeys.lists() }),
  });
}

export function useDeleteTaxonList() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (listId: string) => deleteTaxonList(listId),
    onSuccess: (_data, listId) =>
      Promise.all([
        qc.invalidateQueries({ queryKey: taxonListKeys.lists() }),
        qc.removeQueries({ queryKey: taxonListKeys.entries(listId) }),
      ]),
  });
}

/**
 * Every entry of a list, for views that show or look up the whole list.
 * Errors (never truncates) if the list is larger than one full page — use
 * useTaxonListPage for lists that can grow that large.
 */
export function useAllTaxonListEntries(listId: string, superkingdom: string | null = null) {
  return useQuery({
    queryKey: taxonListKeys.allEntries(listId, superkingdom),
    queryFn: () => getAllTaxonListEntries(listId, superkingdom),
  });
}

/** One page of a list's entries, with the total — for browsing large lists. */
export function useTaxonListPage(listId: string, params: EntryPageParams) {
  return useQuery({
    queryKey: taxonListKeys.entryPage(listId, params),
    queryFn: () => getTaxonListEntryPage(listId, params),
    // Keep the current page on screen while the next one loads.
    placeholderData: keepPreviousData,
  });
}

export function useAddTaxonListEntry(listId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entry: NewTaxonListEntry) => addTaxonListEntry(listId, entry),
    onSuccess: () => invalidateList(qc, listId),
  });
}

/** Preview (`dryRun`) or add many taxa; only a real run refreshes the list. */
export function useBulkAddTaxonListEntries(listId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (request: BulkAddTaxonListEntries) => bulkAddTaxonListEntries(listId, request),
    onSuccess: (report) => (report.added > 0 ? invalidateList(qc, listId) : undefined),
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
