import client from "./client";
import type { Outbreak, OutbreaksResponse } from "./types";

interface RawConfigResult {
  config_name?: string;
  superkingdoms?: string[];
  outbreaks?: Outbreak[];
}

interface RawOutbreaksResponse {
  window_days: number;
  results?: RawConfigResult[];
  outbreaks?: Outbreak[];
}

export async function getOutbreaks(
  windowDays = 14,
  analysisTypes: string[] | null = null
): Promise<OutbreaksResponse> {
  const params: Record<string, unknown> = { window_days: windowDays };
  if (analysisTypes && analysisTypes.length > 0) {
    params.analysis_types = analysisTypes;
  }
  const res = await client.get<RawOutbreaksResponse>("/alerts/outbreaks", {
    params,
    // FastAPI list[str] expects repeated ?analysis_types=shotgun&analysis_types=amplicon
    paramsSerializer: { indexes: null },
  });
  // Transform the new response format into a flat list of outbreaks
  // New API returns: { results: [{ config_name, outbreaks: [...] }, ...] }
  // Frontend expects: { outbreaks: [...] } for backward compatibility
  const data = res.data;
  if (data.results && Array.isArray(data.results)) {
    const allOutbreaks: Outbreak[] = [];
    for (const configResult of data.results) {
      for (const outbreak of configResult.outbreaks || []) {
        allOutbreaks.push({
          ...outbreak,
          config_name: configResult.config_name,
          superkingdoms: configResult.superkingdoms,
        });
      }
    }
    return {
      window_days: data.window_days,
      outbreaks: allOutbreaks,
    };
  }
  return {
    window_days: data.window_days,
    outbreaks: data.outbreaks ?? [],
  };
}
