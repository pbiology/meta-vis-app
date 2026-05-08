import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addNtcContaminant,
  addToNtcIgnorelist,
  getNtcContaminantAlerts,
  getNtcContaminantCaseIds,
  getNtcContaminants,
  getNtcIgnorelist,
  getNtcTrends,
  removeFromNtcIgnorelist,
  removeNtcContaminant,
  updateNtcContaminant,
  updateNtcIgnorelistNote,
  type GetNtcTrendsParams,
  type UpdateNtcContaminantFields,
} from "../../api/ntc";

export const ntcKeys = {
  all: ["ntc"] as const,
  trends: (params: GetNtcTrendsParams) => ["ntc", "trends", params] as const,
  ignorelist: () => ["ntc", "ignorelist"] as const,
  contaminants: () => ["ntc", "contaminants"] as const,
  contaminantAlerts: () => ["ntc", "contaminantAlerts"] as const,
  contaminantCaseIds: () => ["ntc", "contaminantCaseIds"] as const,
};

export function useNtcTrends(params: GetNtcTrendsParams) {
  return useQuery({
    queryKey: ntcKeys.trends(params),
    queryFn: () => getNtcTrends(params),
    enabled: Boolean(params.material),
  });
}

export function useNtcIgnorelist() {
  return useQuery({
    queryKey: ntcKeys.ignorelist(),
    queryFn: () => getNtcIgnorelist(),
  });
}

export function useNtcContaminants() {
  return useQuery({
    queryKey: ntcKeys.contaminants(),
    queryFn: () => getNtcContaminants(),
  });
}

export function useNtcContaminantAlerts() {
  return useQuery({
    queryKey: ntcKeys.contaminantAlerts(),
    queryFn: () => getNtcContaminantAlerts(),
  });
}

export function useNtcContaminantCaseIds() {
  return useQuery({
    queryKey: ntcKeys.contaminantCaseIds(),
    queryFn: () => getNtcContaminantCaseIds(),
  });
}

export function useAddToNtcIgnorelist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      taxonId,
      taxonName,
      superkingdom,
      reason = null,
    }: {
      taxonId: number;
      taxonName: string;
      superkingdom: string;
      reason?: string | null;
    }) => addToNtcIgnorelist(taxonId, taxonName, superkingdom, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: ntcKeys.ignorelist() }),
  });
}

export function useUpdateNtcIgnorelistNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taxonId, reason }: { taxonId: number; reason: string | null }) =>
      updateNtcIgnorelistNote(taxonId, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: ntcKeys.ignorelist() }),
  });
}

export function useRemoveFromNtcIgnorelist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taxonId: number) => removeFromNtcIgnorelist(taxonId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ntcKeys.ignorelist() }),
  });
}

export function useAddNtcContaminant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      taxonId,
      taxonName,
      superkingdom,
      minReads,
      notes = null,
    }: {
      taxonId: number;
      taxonName: string;
      superkingdom: string;
      minReads?: number;
      notes?: string | null;
    }) => addNtcContaminant(taxonId, taxonName, superkingdom, minReads, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: ntcKeys.contaminants() }),
  });
}

export function useUpdateNtcContaminant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taxonId, fields }: { taxonId: number; fields: UpdateNtcContaminantFields }) =>
      updateNtcContaminant(taxonId, fields),
    onSuccess: () => qc.invalidateQueries({ queryKey: ntcKeys.contaminants() }),
  });
}

export function useRemoveNtcContaminant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taxonId: number) => removeNtcContaminant(taxonId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ntcKeys.contaminants() }),
  });
}
