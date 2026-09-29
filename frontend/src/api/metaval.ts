import client from "./client";
import type { MetavalDetail, MetavalSummary } from "./types";

export async function getMetavalForSample(sampleId: string): Promise<MetavalSummary[]> {
  const res = await client.get<MetavalSummary[]>(`/metaval/sample/${sampleId}`);
  return res.data;
}

export async function getMetavalResult(metavalId: string): Promise<MetavalDetail> {
  const res = await client.get<MetavalDetail>(`/metaval/${metavalId}`);
  return res.data;
}

export interface BlastSubmitResponse {
  results_url: string;
  [key: string]: unknown;
}

export async function submitBlast(metavalId: string): Promise<BlastSubmitResponse> {
  const res = await client.post<BlastSubmitResponse>(`/metaval/${metavalId}/blast`);
  return res.data;
}

export async function getIgvUrl(metavalId: string, organismName: string): Promise<string> {
  const res = await client.get<Blob>(
    `/metaval/${metavalId}/igv/${encodeURIComponent(organismName)}`,
    {
      responseType: "blob",
    }
  );
  return URL.createObjectURL(res.data);
}
