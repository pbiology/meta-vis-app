import { useQuery } from "@tanstack/react-query";
import {
  getNtcContaminantAlerts,
  getNtcContaminantCaseIds,
  getNtcTrends,
  type GetNtcTrendsParams,
} from "../../api/ntc";

export const ntcKeys = {
  all: ["ntc"] as const,
  trends: (params: GetNtcTrendsParams) => ["ntc", "trends", params] as const,
  contaminantAlerts: () => ["ntc", "contaminantAlerts"] as const,
  contaminantCaseIds: () => ["ntc", "contaminantCaseIds"] as const,
};

export function useNtcTrends(params: GetNtcTrendsParams) {
  return useQuery({
    queryKey: ntcKeys.trends(params),
    queryFn: () => getNtcTrends(params),
    enabled: Boolean(params.nucleicAcid),
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
