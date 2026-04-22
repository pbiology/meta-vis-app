import client from "./client";
import type { Sample } from "./types";

export interface GetSamplesParams {
  page?: number;
  search?: string;
  filter?: string;
  analysisType?: string | null;
}

export async function getSamples({
  page = 1,
  search = "",
  filter = "",
  analysisType,
}: GetSamplesParams = {}): Promise<unknown> {
  const params: Record<string, unknown> = { page, search, filter };
  if (analysisType) params.analysis_type = analysisType;
  const res = await client.get("/samples", { params });
  return res.data;
}

export async function getSample(sampleId: string): Promise<Sample> {
  const res = await client.get<Sample>(`/samples/${sampleId}`);
  return res.data;
}

export async function getProfile(sampleId: string): Promise<unknown> {
  const res = await client.get(`/samples/${sampleId}/profile`);
  return res.data;
}

export async function getKronaUrl(sampleId: string, classifier = "kraken2"): Promise<string> {
  const resp = await client.get<Blob>(`/samples/${sampleId}/krona`, {
    params: { classifier },
    responseType: "blob",
  });
  return URL.createObjectURL(resp.data);
}

export async function getNtcProfiles(sampleId: string): Promise<unknown> {
  const res = await client.get(`/samples/${sampleId}/ntc_profiles`);
  return res.data;
}
