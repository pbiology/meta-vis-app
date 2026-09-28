import { useQuery } from "@tanstack/react-query";
import { getOutbreaks } from "../../api/alerts";

export const alertKeys = {
  all: ["alerts"] as const,
  outbreaks: (windowDays: number, analysisTypes: string[] | null = null) =>
    ["alerts", "outbreaks", { windowDays, analysisTypes }] as const,
};

export function useOutbreaks(windowDays = 14, analysisTypes: string[] | null = null) {
  return useQuery({
    queryKey: alertKeys.outbreaks(windowDays, analysisTypes),
    queryFn: () => getOutbreaks(windowDays, analysisTypes),
  });
}
