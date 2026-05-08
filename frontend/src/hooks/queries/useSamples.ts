import { useQuery } from "@tanstack/react-query";
import {
  getKronaUrl,
  getNtcProfiles,
  getProfile,
  getSample,
  getSamples,
  type GetSamplesParams,
} from "../../api/samples";

export const sampleKeys = {
  all: ["samples"] as const,
  list: (params: GetSamplesParams) => ["samples", "list", params] as const,
  detail: (sampleId: string) => ["samples", "detail", sampleId] as const,
  profile: (sampleId: string) => ["samples", sampleId, "profile"] as const,
  ntcProfiles: (sampleId: string) => ["samples", sampleId, "ntcProfiles"] as const,
  krona: (sampleId: string, classifier: string) =>
    ["samples", sampleId, "krona", classifier] as const,
};

interface UseSampleOptions {
  enabled?: boolean;
}

export function useSamples(params: GetSamplesParams = {}) {
  return useQuery({
    queryKey: sampleKeys.list(params),
    queryFn: () => getSamples(params),
  });
}

export function useSample(sampleId: string, opts: UseSampleOptions = {}) {
  return useQuery({
    queryKey: sampleKeys.detail(sampleId),
    queryFn: () => getSample(sampleId),
    enabled: (opts.enabled ?? true) && Boolean(sampleId),
  });
}

export function useSampleProfile(sampleId: string, opts: UseSampleOptions = {}) {
  return useQuery({
    queryKey: sampleKeys.profile(sampleId),
    queryFn: () => getProfile(sampleId),
    enabled: (opts.enabled ?? true) && Boolean(sampleId),
  });
}

export function useNtcProfiles(sampleId: string, opts: UseSampleOptions = {}) {
  return useQuery({
    queryKey: sampleKeys.ntcProfiles(sampleId),
    queryFn: () => getNtcProfiles(sampleId),
    enabled: (opts.enabled ?? true) && Boolean(sampleId),
  });
}

// Returns a blob URL; callers must revoke on unmount. `gcTime: 0` ensures the
// cache drops the URL when no observers remain so a stale (revoked) URL is
// never re-served.
export function useSampleKronaUrl(
  sampleId: string,
  classifier = "kraken2",
  opts: UseSampleOptions = {}
) {
  return useQuery({
    queryKey: sampleKeys.krona(sampleId, classifier),
    queryFn: () => getKronaUrl(sampleId, classifier),
    enabled: (opts.enabled ?? true) && Boolean(sampleId),
    gcTime: 0,
  });
}
