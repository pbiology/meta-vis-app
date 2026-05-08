import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addToIgnorelist,
  addToPathogens,
  getIgnorelist,
  getOutbreaks,
  getPathogens,
  removeFromIgnorelist,
  removeFromPathogens,
  updateIgnorelistNote,
} from "../../api/alerts";

export const alertKeys = {
  all: ["alerts"] as const,
  outbreaks: (windowDays: number, analysisTypes: string[] | null = null) =>
    ["alerts", "outbreaks", { windowDays, analysisTypes }] as const,
  ignorelist: (superkingdom: string | null = null) =>
    ["alerts", "ignorelist", superkingdom] as const,
  pathogens: () => ["alerts", "pathogens"] as const,
};

export function useOutbreaks(windowDays = 14, analysisTypes: string[] | null = null) {
  return useQuery({
    queryKey: alertKeys.outbreaks(windowDays, analysisTypes),
    queryFn: () => getOutbreaks(windowDays, analysisTypes),
  });
}

export function useIgnorelist(superkingdom: string | null = null) {
  return useQuery({
    queryKey: alertKeys.ignorelist(superkingdom),
    queryFn: () => getIgnorelist(superkingdom),
  });
}

export function usePathogens() {
  return useQuery({
    queryKey: alertKeys.pathogens(),
    queryFn: () => getPathogens(),
  });
}

export function useAddToIgnorelist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      taxonId,
      taxonName,
      superkingdom = "Viruses",
      reason = null,
    }: {
      taxonId: number;
      taxonName: string;
      superkingdom?: string;
      reason?: string | null;
    }) => addToIgnorelist(taxonId, taxonName, superkingdom, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: alertKeys.all }),
  });
}

export function useRemoveFromIgnorelist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taxonId: number) => removeFromIgnorelist(taxonId),
    onSuccess: () => qc.invalidateQueries({ queryKey: alertKeys.all }),
  });
}

export function useUpdateIgnorelistNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taxonId, reason }: { taxonId: number; reason: string | null }) =>
      updateIgnorelistNote(taxonId, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: alertKeys.ignorelist() }),
  });
}

export function useAddToPathogens() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      taxonId,
      taxonName,
      superkingdom = "Viruses",
      notes = null,
    }: {
      taxonId: number;
      taxonName: string;
      superkingdom?: string;
      notes?: string | null;
    }) => addToPathogens(taxonId, taxonName, superkingdom, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: alertKeys.pathogens() }),
  });
}

export function useRemoveFromPathogens() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taxonId: number) => removeFromPathogens(taxonId),
    onSuccess: () => qc.invalidateQueries({ queryKey: alertKeys.pathogens() }),
  });
}
