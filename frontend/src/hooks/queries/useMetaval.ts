import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getIgvUrl, getMetavalForSample, getMetavalResult, submitBlast } from "../../api/metaval";

export const metavalKeys = {
  all: ["metaval"] as const,
  bySample: (sampleId: string) => ["metaval", "bySample", sampleId] as const,
  detail: (metavalId: string) => ["metaval", "detail", metavalId] as const,
  igv: (metavalId: string, organismName: string) =>
    ["metaval", metavalId, "igv", organismName] as const,
};

interface UseMetavalOptions {
  enabled?: boolean;
}

export function useMetavalForSample(sampleId: string, opts: UseMetavalOptions = {}) {
  return useQuery({
    queryKey: metavalKeys.bySample(sampleId),
    queryFn: () => getMetavalForSample(sampleId),
    enabled: (opts.enabled ?? true) && Boolean(sampleId),
  });
}

export function useMetavalResult(metavalId: string, opts: UseMetavalOptions = {}) {
  return useQuery({
    queryKey: metavalKeys.detail(metavalId),
    queryFn: () => getMetavalResult(metavalId),
    enabled: (opts.enabled ?? true) && Boolean(metavalId),
  });
}

// Returns a blob URL; callers must revoke on unmount. `gcTime: 0` ensures the
// cache drops the URL when no observers remain so a stale (revoked) URL is
// never re-served.
export function useIgvUrl(metavalId: string, organismName: string, opts: UseMetavalOptions = {}) {
  return useQuery({
    queryKey: metavalKeys.igv(metavalId, organismName),
    queryFn: () => getIgvUrl(metavalId, organismName),
    enabled: (opts.enabled ?? true) && Boolean(metavalId) && Boolean(organismName),
    gcTime: 0,
  });
}

export function useSubmitBlast() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (metavalId: string) => submitBlast(metavalId),
    onSuccess: (_data, metavalId) =>
      qc.invalidateQueries({ queryKey: metavalKeys.detail(metavalId) }),
  });
}
