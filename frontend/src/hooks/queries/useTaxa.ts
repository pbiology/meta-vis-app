import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getBvbrcGenomes,
  getBvbrcSpecialtyGenes,
  getTaxon,
  getTaxonExternalLinks,
  getTaxonLiterature,
  getTaxonOccurrences,
  updateClinicalNotes,
  type TaxonId,
} from "../../api/taxa";

export const taxonKeys = {
  all: ["taxa"] as const,
  detail: (taxonId: TaxonId) => ["taxa", "detail", String(taxonId)] as const,
  occurrences: (taxonId: TaxonId, windowDays: number) =>
    ["taxa", String(taxonId), "occurrences", windowDays] as const,
  externalLinks: (taxonId: TaxonId) => ["taxa", String(taxonId), "externalLinks"] as const,
  literature: (taxonId: TaxonId, maxResults: number) =>
    ["taxa", String(taxonId), "literature", maxResults] as const,
  bvbrcGenomes: (taxonId: TaxonId) => ["taxa", String(taxonId), "bvbrcGenomes"] as const,
  bvbrcSpecialtyGenes: (taxonId: TaxonId) =>
    ["taxa", String(taxonId), "bvbrcSpecialtyGenes"] as const,
};

export function useTaxon(taxonId: TaxonId) {
  return useQuery({
    queryKey: taxonKeys.detail(taxonId),
    queryFn: () => getTaxon(taxonId),
    enabled: taxonId !== "" && taxonId !== null && taxonId !== undefined,
  });
}

export function useTaxonOccurrences(taxonId: TaxonId, windowDays = 90) {
  return useQuery({
    queryKey: taxonKeys.occurrences(taxonId, windowDays),
    queryFn: () => getTaxonOccurrences(taxonId, windowDays),
  });
}

export function useTaxonExternalLinks(taxonId: TaxonId) {
  return useQuery({
    queryKey: taxonKeys.externalLinks(taxonId),
    queryFn: () => getTaxonExternalLinks(taxonId),
  });
}

export function useTaxonLiterature(taxonId: TaxonId, maxResults = 5) {
  return useQuery({
    queryKey: taxonKeys.literature(taxonId, maxResults),
    queryFn: () => getTaxonLiterature(taxonId, maxResults),
  });
}

export function useBvbrcGenomes(taxonId: TaxonId) {
  return useQuery({
    queryKey: taxonKeys.bvbrcGenomes(taxonId),
    queryFn: () => getBvbrcGenomes(taxonId),
  });
}

export function useBvbrcSpecialtyGenes(taxonId: TaxonId) {
  return useQuery({
    queryKey: taxonKeys.bvbrcSpecialtyGenes(taxonId),
    queryFn: () => getBvbrcSpecialtyGenes(taxonId),
  });
}

export function useUpdateClinicalNotes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taxonId, clinicalNotes }: { taxonId: TaxonId; clinicalNotes: string | null }) =>
      updateClinicalNotes(taxonId, clinicalNotes),
    onSuccess: (_data, { taxonId }) =>
      qc.invalidateQueries({ queryKey: taxonKeys.detail(taxonId) }),
  });
}
