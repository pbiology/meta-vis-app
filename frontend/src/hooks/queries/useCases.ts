import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addNote,
  deleteCase,
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
} from "../../api/cases";

export const caseKeys = {
  all: ["cases"] as const,
  list: (params: GetCasesParams) => ["cases", "list", params] as const,
  stats: () => ["cases", "stats"] as const,
  pathogenCases: () => ["cases", "pathogenCases"] as const,
  detail: (caseId: string) => ["cases", "detail", caseId] as const,
  samples: (caseId: string, type: string | null) => ["cases", caseId, "samples", type] as const,
  krona: (caseId: string, classifier: string) => ["cases", caseId, "krona", classifier] as const,
  multiqc: (caseId: string) => ["cases", caseId, "multiqc"] as const,
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

export function useCase(caseId: string) {
  return useQuery({
    queryKey: caseKeys.detail(caseId),
    queryFn: () => getCase(caseId),
    enabled: Boolean(caseId),
  });
}

export function useCaseSamples(caseId: string, type: string | null = null) {
  return useQuery({
    queryKey: caseKeys.samples(caseId, type),
    queryFn: () => getCaseSamples(caseId, type),
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
export function useCaseKronaUrl(caseId: string, classifier = "kraken2") {
  return useQuery({
    queryKey: caseKeys.krona(caseId, classifier),
    queryFn: () => getCaseKronaUrl(caseId, classifier),
    enabled: Boolean(caseId),
    gcTime: 0,
  });
}

export function useCaseMultiQCUrl(caseId: string) {
  return useQuery({
    queryKey: caseKeys.multiqc(caseId),
    queryFn: () => getCaseMultiQCUrl(caseId),
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

export function useReviewCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ caseId, notes }: { caseId: string; notes?: string | null }) =>
      reviewCase(caseId, notes ?? null),
    onSuccess: () => qc.invalidateQueries({ queryKey: caseKeys.all }),
  });
}

export function useUnreviewCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (caseId: string) => unreviewCase(caseId),
    onSuccess: () => qc.invalidateQueries({ queryKey: caseKeys.all }),
  });
}

export function useAddCaseNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ caseId, text }: { caseId: string; text: string }) => addNote(caseId, text),
    onSuccess: (_data, { caseId }) => qc.invalidateQueries({ queryKey: caseKeys.detail(caseId) }),
  });
}

export function useDeleteCaseNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ caseId, noteId }: { caseId: string; noteId: string }) =>
      deleteNote(caseId, noteId),
    onSuccess: (_data, { caseId }) => qc.invalidateQueries({ queryKey: caseKeys.detail(caseId) }),
  });
}

export function useUpdateCaseReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      caseId,
      selections,
    }: {
      caseId: string;
      selections: Record<string, number[]>;
    }) => updateCaseReport(caseId, selections),
    onSuccess: (_data, { caseId }) => qc.invalidateQueries({ queryKey: caseKeys.detail(caseId) }),
  });
}
