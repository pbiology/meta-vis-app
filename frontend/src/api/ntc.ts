import client from "./client";
import type { NtcContaminantAlertsResponse, NtcTrendsResponse } from "./types";

export interface GetNtcTrendsParams {
  nucleicAcid: string;
  windowDays?: number;
  minReads?: number;
  minControlPct?: number;
  pipeline?: string;
}

export async function getNtcTrends({
  nucleicAcid,
  windowDays = 90,
  minReads = 3,
  minControlPct = 0.1,
  pipeline = "taxprofiler",
}: GetNtcTrendsParams): Promise<NtcTrendsResponse> {
  const res = await client.get<NtcTrendsResponse>("/ntc/trends", {
    params: {
      nucleic_acid: nucleicAcid,
      window_days: windowDays,
      min_reads: minReads,
      min_control_pct: minControlPct,
      pipeline,
    },
  });
  return res.data;
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
