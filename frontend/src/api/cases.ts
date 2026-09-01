import client from "./client";
import type { CaseDetail, CaseStats, CasesResponse, Sample } from "./types";

export type ReviewedFilter = "reviewed" | "unreviewed" | "pending" | "all" | null;

export interface GetCasesParams {
  page?: number;
  search?: string;
  reviewed?: ReviewedFilter;
  analysisType?: string | null;
}

/**
 * Base path for run-scoped resources. Omitting the version resolves to the
 * case's latest analysis, which is what every view wants by default.
 */
function analysisPath(caseId: string, version?: number | null): string {
  return version == null ? `/cases/${caseId}` : `/cases/${caseId}/analyses/${version}`;
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

export async function getCase(caseId: string, version?: number | null): Promise<CaseDetail> {
  const res = await client.get<CaseDetail>(analysisPath(caseId, version));
  return res.data;
}

export async function getCaseSamples(
  caseId: string,
  type: string | null = null,
  version?: number | null
): Promise<Sample[]> {
  const params = type ? { type } : {};
  const res = await client.get<Sample[]>(`${analysisPath(caseId, version)}/samples`, {
    params,
  });
  return res.data;
}

export async function reviewCase(
  caseId: string,
  notes: string | null = null,
  version?: number | null
): Promise<unknown> {
  const res = await client.patch(`${analysisPath(caseId, version)}/review`, { notes });
  return res.data;
}

export async function unreviewCase(caseId: string, version?: number | null): Promise<unknown> {
  const res = await client.delete(`${analysisPath(caseId, version)}/review`);
  return res.data;
}

export async function getCaseKronaUrl(
  caseId: string,
  classifier = "kraken2",
  version?: number | null
): Promise<string> {
  const resp = await client.get<Blob>(`${analysisPath(caseId, version)}/krona`, {
    params: { classifier },
    responseType: "blob",
  });
  return URL.createObjectURL(resp.data);
}

export async function getCaseMultiQCUrl(caseId: string, version?: number | null): Promise<string> {
  const resp = await client.get<Blob>(`${analysisPath(caseId, version)}/multiqc`, {
    responseType: "blob",
  });
  return URL.createObjectURL(resp.data);
}

// Notes belong to the case, not to a run, so they carry no version.
export async function addNote(caseId: string, text: string): Promise<unknown> {
  const res = await client.post(`/cases/${caseId}/notes`, { text });
  return res.data;
}

export async function deleteNote(caseId: string, noteId: string): Promise<unknown> {
  const res = await client.delete(`/cases/${caseId}/notes/${noteId}`);
  return res.data;
}

export async function deleteCase(caseId: string): Promise<void> {
  await client.delete(`/cases/${caseId}`);
}

export async function deleteCaseAnalysis(caseId: string, version: number): Promise<void> {
  await client.delete(`/cases/${caseId}/analyses/${version}`);
}

export async function getCaseStats(): Promise<CaseStats> {
  const res = await client.get<CaseStats>("/cases/stats");
  return res.data;
}

export interface UpdateCaseReportResponse {
  case_id: string;
  version: number;
  selections: Record<string, number[]>;
}

export async function updateCaseReport(
  caseId: string,
  selections: Record<string, number[]>,
  version?: number | null
): Promise<UpdateCaseReportResponse> {
  const res = await client.patch<UpdateCaseReportResponse>(
    `${analysisPath(caseId, version)}/report`,
    { selections }
  );
  return res.data;
}

export interface CarryForwardDropped {
  sample_id: string;
  reason: string;
  taxon_ids?: number[];
}

export interface CarryForwardResponse {
  case_id: string;
  version: number;
  from_version: number;
  applied: Record<string, number[]>;
  dropped: CarryForwardDropped[];
}

/** Copy an earlier run's report picks into this one, dropping what no longer applies. */
export async function carryForwardReport(
  caseId: string,
  version: number,
  fromVersion: number
): Promise<CarryForwardResponse> {
  const res = await client.post<CarryForwardResponse>(
    `/cases/${caseId}/analyses/${version}/report/carry-forward`,
    null,
    { params: { from_version: fromVersion } }
  );
  return res.data;
}

export async function getPathogenCases(): Promise<{ case_ids: string[] }> {
  const res = await client.get<{ case_ids: string[] }>("/cases/pathogen_cases");
  return res.data;
}
