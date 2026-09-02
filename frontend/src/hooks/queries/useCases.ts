import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addNote,
  carryForwardReport,
  deleteCase,
  deleteCaseAnalysis,
  deleteNote,
  getCase,
  getCaseKronaUrl,
  getCaseMultiQCUrl,
  getCaseSamples,
  getCaseStats,
  getCases,
  getPathogenCases,
  reviewCase,
  unreviewCase,
  updateCaseReport,
  type GetCasesParams,
  type Version,
} from "../../api/cases";

/**
 * Run-scoped keys carry the analysis version so switching versions refetches
 * rather than serving another run's cached data. `null` means "latest" and is
 * a distinct key from an explicit version, which is fine: both resolve to the
 * same data and invalidation clears them together.
 *
 * Every run-scoped hook takes it as a *required* argument — see the note in
 * api/cases.ts on why a default was the wrong call.
 */

export const caseKeys = {
  all: ["cases"] as const,
  list: (params: GetCasesParams) => ["cases", "list", params] as const,
  stats: () => ["cases", "stats"] as const,
  pathogenCases: () => ["cases", "pathogenCases"] as const,

  // Every per-case query hangs off `case(caseId)`, so invalidating that prefix
  // reaches all of them whatever version they carry. React Query matches keys
  // by prefix, so the caseId has to sit at the same position in each — when
  // `detail` had its own shape, invalidating a case silently missed it and
  // notes only appeared after a manual refresh.
  //
  // The literal "case" segment keeps a case named "list" or "stats" from
  // colliding with the collection-level keys above.
  case: (caseId: string) => ["cases", "case", caseId] as const,
  detail: (caseId: string, version: Version) =>
    [...caseKeys.case(caseId), "detail", version] as const,
  samples: (caseId: string, type: string | null, version: Version) =>
    [...caseKeys.case(caseId), "samples", type, version] as const,
  krona: (caseId: string, classifier: string, version: Version) =>
    [...caseKeys.case(caseId), "krona", classifier, version] as const,
  multiqc: (caseId: string, version: Version) =>
    [...caseKeys.case(caseId), "multiqc", version] as const,
};

interface PollOptions {
  refetchInterval?: number;
}

export function useCases(params: GetCasesParams = {}, opts: PollOptions = {}) {
  return useQuery({
    queryKey: caseKeys.list(params),
    queryFn: () => getCases(params),
    refetchInterval: opts.refetchInterval,
  });
}

export function useCase(caseId: string, version: Version) {
  return useQuery({
    queryKey: caseKeys.detail(caseId, version),
    queryFn: () => getCase(caseId, version),
    enabled: Boolean(caseId),
  });
}

export function useCaseSamples(caseId: string, type: string | null, version: Version) {
  return useQuery({
    queryKey: caseKeys.samples(caseId, type, version),
    queryFn: () => getCaseSamples(caseId, type, version),
    enabled: Boolean(caseId),
  });
}

export function useCaseStats(opts: PollOptions = {}) {
  return useQuery({
    queryKey: caseKeys.stats(),
    queryFn: () => getCaseStats(),
    refetchInterval: opts.refetchInterval,
  });
}

export function usePathogenCases() {
  return useQuery({
    queryKey: caseKeys.pathogenCases(),
    queryFn: () => getPathogenCases(),
  });
}

// Krona / MultiQC fetches return blob URLs; callers must revoke on unmount.
// `gcTime: 0` makes the cache drop the URL the moment no observers remain, so
// stale (revoked) blob URLs can't be re-served on a later mount.
export function useCaseKronaUrl(caseId: string, classifier: string, version: Version) {
  return useQuery({
    queryKey: caseKeys.krona(caseId, classifier, version),
    queryFn: () => getCaseKronaUrl(caseId, classifier, version),
    enabled: Boolean(caseId),
    gcTime: 0,
  });
}

export function useCaseMultiQCUrl(caseId: string, version: Version) {
  return useQuery({
    queryKey: caseKeys.multiqc(caseId, version),
    queryFn: () => getCaseMultiQCUrl(caseId, version),
    enabled: Boolean(caseId),
    gcTime: 0,
  });
}

export function useDeleteCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (caseId: string) => deleteCase(caseId),
    onSuccess: () => qc.invalidateQueries({ queryKey: caseKeys.all }),
  });
}

export function useDeleteCaseAnalysis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ caseId, version }: { caseId: string; version: number }) =>
      deleteCaseAnalysis(caseId, version),
    onSuccess: () => qc.invalidateQueries({ queryKey: caseKeys.all }),
  });
}

export function useReviewCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      caseId,
      notes,
      version,
    }: {
      caseId: string;
      notes?: string | null;
      version: Version;
    }) => reviewCase(caseId, notes ?? null, version),
    onSuccess: () => qc.invalidateQueries({ queryKey: caseKeys.all }),
  });
}

export function useUnreviewCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ caseId, version }: { caseId: string; version: Version }) =>
      unreviewCase(caseId, version),
    onSuccess: () => qc.invalidateQueries({ queryKey: caseKeys.all }),
  });
}

export function useAddCaseNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ caseId, text }: { caseId: string; text: string }) => addNote(caseId, text),
    onSuccess: (_data, { caseId }) => qc.invalidateQueries({ queryKey: caseKeys.case(caseId) }),
  });
}

export function useDeleteCaseNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ caseId, noteId }: { caseId: string; noteId: string }) =>
      deleteNote(caseId, noteId),
    onSuccess: (_data, { caseId }) => qc.invalidateQueries({ queryKey: caseKeys.case(caseId) }),
  });
}

export function useUpdateCaseReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      caseId,
      selections,
      version,
    }: {
      caseId: string;
      selections: Record<string, number[]>;
      version: Version;
    }) => updateCaseReport(caseId, selections, version),
    onSuccess: (_data, { caseId }) => qc.invalidateQueries({ queryKey: caseKeys.case(caseId) }),
  });
}

export function useCarryForwardReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      caseId,
      version,
      fromVersion,
    }: {
      caseId: string;
      version: number;
      fromVersion: number;
    }) => carryForwardReport(caseId, version, fromVersion),
    onSuccess: (_data, { caseId }) => qc.invalidateQueries({ queryKey: caseKeys.case(caseId) }),
  });
}
