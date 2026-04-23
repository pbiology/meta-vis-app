import client from "./client";
import type {
  IgnorelistItem,
  NtcContaminantAlertsResponse,
  NtcContaminantItem,
  NtcTrendsResponse,
} from "./types";

export interface GetNtcTrendsParams {
  material: string;
  windowDays?: number;
  minReads?: number;
  minCasePct?: number;
  pipeline?: string;
}

export async function getNtcTrends({
  material,
  windowDays = 90,
  minReads = 3,
  minCasePct = 0.1,
  pipeline = "taxprofiler",
}: GetNtcTrendsParams): Promise<NtcTrendsResponse> {
  const res = await client.get<NtcTrendsResponse>("/ntc/trends", {
    params: {
      material,
      window_days: windowDays,
      min_reads: minReads,
      min_case_pct: minCasePct,
      pipeline,
    },
  });
  return res.data;
}

// --- Ignorelist ---

export async function getNtcIgnorelist(): Promise<IgnorelistItem[]> {
  const res = await client.get<IgnorelistItem[]>("/ntc/ignorelist");
  return res.data;
}

export async function addToNtcIgnorelist(
  taxonId: number,
  taxonName: string,
  superkingdom: string,
  reason: string | null = null
): Promise<IgnorelistItem> {
  const res = await client.post<IgnorelistItem>("/ntc/ignorelist", {
    taxon_id: taxonId,
    taxon_name: taxonName,
    superkingdom,
    reason,
  });
  return res.data;
}

export async function updateNtcIgnorelistNote(
  taxonId: number,
  reason: string | null
): Promise<IgnorelistItem> {
  const res = await client.patch<IgnorelistItem>(`/ntc/ignorelist/${taxonId}`, { reason });
  return res.data;
}

export async function removeFromNtcIgnorelist(taxonId: number): Promise<void> {
  await client.delete(`/ntc/ignorelist/${taxonId}`);
}

// --- Known contaminants ---

export async function getNtcContaminants(): Promise<NtcContaminantItem[]> {
  const res = await client.get<NtcContaminantItem[]>("/ntc/contaminants");
  return res.data;
}

export async function addNtcContaminant(
  taxonId: number,
  taxonName: string,
  superkingdom: string,
  minReads = 3,
  notes: string | null = null
): Promise<NtcContaminantItem> {
  const res = await client.post<NtcContaminantItem>("/ntc/contaminants", {
    taxon_id: taxonId,
    taxon_name: taxonName,
    superkingdom,
    min_reads: minReads,
    notes,
  });
  return res.data;
}

export interface UpdateNtcContaminantFields {
  minReads?: number;
  notes?: string | null;
}

export async function updateNtcContaminant(
  taxonId: number,
  { minReads, notes }: UpdateNtcContaminantFields
): Promise<NtcContaminantItem> {
  const res = await client.patch<NtcContaminantItem>(`/ntc/contaminants/${taxonId}`, {
    min_reads: minReads,
    notes,
  });
  return res.data;
}

export async function removeNtcContaminant(taxonId: number): Promise<void> {
  await client.delete(`/ntc/contaminants/${taxonId}`);
}

// --- Contaminant alerts ---

export async function getNtcContaminantAlerts(): Promise<NtcContaminantAlertsResponse> {
  const res = await client.get<NtcContaminantAlertsResponse>("/ntc/contaminant-alerts");
  return res.data;
}

export async function getNtcContaminantCaseIds(): Promise<{ case_ids: string[] }> {
  const res = await client.get<NtcContaminantAlertsResponse>("/ntc/contaminant-alerts");
  return { case_ids: res.data.contaminant_case_ids };
}
