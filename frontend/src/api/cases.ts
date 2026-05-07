import client from "./client";
import type { Case, CaseStats, CasesResponse, Sample } from "./types";

export type ReviewedFilter = "reviewed" | "unreviewed" | "pending" | "all" | null;

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
}: GetCasesParams = {}): Promise<CasesResponse> {
  const params: Record<string, unknown> = { page, search };
  if (reviewed && reviewed !== "all") {
    params.reviewed = reviewed;
  }
  if (analysisType && analysisType !== "all") {
    params.analysis_type = analysisType;
  }
  const res = await client.get<CasesResponse>("/cases", { params });
  return res.data;
}

export async function getCase(caseId: string): Promise<Case> {
  const res = await client.get<Case>(`/cases/${caseId}`);
  return res.data;
}

export async function getCaseSamples(
  caseId: string,
  type: string | null = null
): Promise<Sample[]> {
  const params = type ? { type } : {};
  const res = await client.get<Sample[]>(`/cases/${caseId}/samples`, { params });
  return res.data;
}

export async function reviewCase(caseId: string, notes: string | null = null): Promise<Case> {
  const res = await client.patch<Case>(`/cases/${caseId}/review`, { notes });
  return res.data;
}

export async function unreviewCase(caseId: string): Promise<Case> {
  const res = await client.delete<Case>(`/cases/${caseId}/review`);
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

export async function addNote(caseId: string, text: string): Promise<Case> {
  const res = await client.post<Case>(`/cases/${caseId}/notes`, { text });
  return res.data;
}

export async function deleteNote(caseId: string, noteId: string): Promise<Case> {
  const res = await client.delete<Case>(`/cases/${caseId}/notes/${noteId}`);
  return res.data;
}

export async function deleteCase(caseId: string): Promise<void> {
  await client.delete(`/cases/${caseId}`);
}

export async function getCaseStats(): Promise<CaseStats> {
  const res = await client.get<CaseStats>("/cases/stats");
  return res.data;
}

export interface UpdateCaseReportResponse {
  case_id: string;
  selections: Record<string, number[]>;
}

export async function updateCaseReport(
  caseId: string,
  selections: Record<string, number[]>
): Promise<UpdateCaseReportResponse> {
  const res = await client.patch<UpdateCaseReportResponse>(`/cases/${caseId}/report`, {
    selections,
  });
  return res.data;
}

export async function getPathogenCases(): Promise<{ case_ids: string[] }> {
  const res = await client.get<{ case_ids: string[] }>("/cases/pathogen_cases");
  return res.data;
}
