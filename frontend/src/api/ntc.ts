import client from "./client";

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
}: GetNtcTrendsParams): Promise<unknown> {
  const res = await client.get("/ntc/trends", {
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

export async function getNtcIgnorelist(): Promise<unknown> {
  const res = await client.get("/ntc/ignorelist");
  return res.data;
}

export async function addToNtcIgnorelist(
  taxonId: number,
  taxonName: string,
  superkingdom: string,
  reason: string | null = null
): Promise<unknown> {
  const res = await client.post("/ntc/ignorelist", {
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
): Promise<unknown> {
  const res = await client.patch(`/ntc/ignorelist/${taxonId}`, { reason });
  return res.data;
}

export async function removeFromNtcIgnorelist(taxonId: number): Promise<unknown> {
  const res = await client.delete(`/ntc/ignorelist/${taxonId}`);
  return res.data;
}

// --- Known contaminants ---

export async function getNtcContaminants(): Promise<unknown> {
  const res = await client.get("/ntc/contaminants");
  return res.data;
}

export async function addNtcContaminant(
  taxonId: number,
  taxonName: string,
  superkingdom: string,
  minReads = 3,
  notes: string | null = null
): Promise<unknown> {
  const res = await client.post("/ntc/contaminants", {
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
): Promise<unknown> {
  const res = await client.patch(`/ntc/contaminants/${taxonId}`, {
    min_reads: minReads,
    notes,
  });
  return res.data;
}

export async function removeNtcContaminant(taxonId: number): Promise<unknown> {
  const res = await client.delete(`/ntc/contaminants/${taxonId}`);
  return res.data;
}

// --- Contaminant alerts ---

export async function getNtcContaminantAlerts(): Promise<unknown> {
  const res = await client.get("/ntc/contaminant-alerts");
  return res.data;
}

export async function getNtcContaminantCaseIds(): Promise<{ case_ids: string[] }> {
  const res = await client.get<{ contaminant_case_ids: string[] }>("/ntc/contaminant-alerts");
  return { case_ids: res.data.contaminant_case_ids };
}
