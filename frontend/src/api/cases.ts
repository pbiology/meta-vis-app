import client from "./client";
import type { Case } from "./types";

export type ReviewedFilter = "reviewed" | "unreviewed" | "all" | null;

export interface GetCasesParams {
  page?: number;
  search?: string;
  reviewed?: ReviewedFilter;
  analysisType?: string | null;
}

export async function getCases({
  page = 1,
  search = "",
  reviewed = null,
  analysisType = null,
}: GetCasesParams = {}): Promise<unknown> {
  const params: Record<string, unknown> = { page, search };
  if (reviewed && reviewed !== "all") {
    params.reviewed = reviewed;
  }
  if (analysisType && analysisType !== "all") {
    params.analysis_type = analysisType;
  }
  const res = await client.get("/cases", { params });
  return res.data;
}

export async function getCase(caseId: string): Promise<Case> {
  const res = await client.get<Case>(`/cases/${caseId}`);
  return res.data;
}

export async function getCaseSamples(caseId: string, type: string | null = null): Promise<unknown> {
  const params = type ? { type } : {};
  const res = await client.get(`/cases/${caseId}/samples`, { params });
  return res.data;
}

export async function reviewCase(caseId: string, notes: string | null = null): Promise<unknown> {
  const res = await client.patch(`/cases/${caseId}/review`, { notes });
  return res.data;
}

export async function unreviewCase(caseId: string): Promise<unknown> {
  const res = await client.delete(`/cases/${caseId}/review`);
  return res.data;
}

export async function getCaseKronaUrl(caseId: string, classifier = "kraken2"): Promise<string> {
  const resp = await client.get<Blob>(`/cases/${caseId}/krona`, {
    params: { classifier },
    responseType: "blob",
  });
  return URL.createObjectURL(resp.data);
}

export async function getCaseMultiQCUrl(caseId: string): Promise<string> {
  const resp = await client.get<Blob>(`/cases/${caseId}/multiqc`, {
    responseType: "blob",
  });
  return URL.createObjectURL(resp.data);
}

export async function addNote(caseId: string, text: string): Promise<unknown> {
  const res = await client.post(`/cases/${caseId}/notes`, { text });
  return res.data;
}

export async function deleteNote(caseId: string, noteIndex: number): Promise<unknown> {
  const res = await client.delete(`/cases/${caseId}/notes/${noteIndex}`);
  return res.data;
}

export async function deleteCase(caseId: string): Promise<unknown> {
  const res = await client.delete(`/cases/${caseId}`);
  return res.data;
}

export async function getCaseStats(): Promise<unknown> {
  const res = await client.get("/cases/stats");
  return res.data;
}

export async function getPathogenCases(): Promise<unknown> {
  const res = await client.get("/cases/pathogen_cases");
  return res.data;
}
