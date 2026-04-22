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
): Promise<OutbreaksResponse | RawOutbreaksResponse> {
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
    // Flatten all outbreaks from all configs into a single array
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
  // Fallback if response format is different
  return data;
}

export async function getIgnorelist(superkingdom: string | null = null): Promise<unknown> {
  const params = superkingdom ? { superkingdom } : {};
  const res = await client.get("/alerts/ignorelist", { params });
  return res.data;
}

export async function addToIgnorelist(
  taxonId: number,
  taxonName: string,
  superkingdom = "Viruses",
  reason: string | null = null
): Promise<unknown> {
  const res = await client.post("/alerts/ignorelist", {
    taxon_id: taxonId,
    taxon_name: taxonName,
    superkingdom,
    reason,
  });
  return res.data;
}

export async function removeFromIgnorelist(taxonId: number): Promise<unknown> {
  const res = await client.delete(`/alerts/ignorelist/${taxonId}`);
  return res.data;
}

export async function updateIgnorelistNote(
  taxonId: number,
  reason: string | null
): Promise<unknown> {
  const res = await client.patch(`/alerts/ignorelist/${taxonId}`, { reason });
  return res.data;
}

export async function getPathogens(): Promise<unknown> {
  const res = await client.get("/alerts/pathogens");
  return res.data;
}

export async function addToPathogens(
  taxonId: number,
  taxonName: string,
  superkingdom = "Viruses",
  notes: string | null = null
): Promise<unknown> {
  const res = await client.post("/alerts/pathogens", {
    taxon_id: taxonId,
    taxon_name: taxonName,
    superkingdom,
    reason: notes,
  });
  return res.data;
}

export async function removeFromPathogens(taxonId: number): Promise<unknown> {
  const res = await client.delete(`/alerts/pathogens/${taxonId}`);
  return res.data;
}
