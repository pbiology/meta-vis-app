import client from "./client";
import type { CaseListItem } from "./types";

export interface Subject {
  subject_id: string;
  sex: "F" | "M" | "X" | "unknown";
  [key: string]: unknown;
}

export interface SubjectListItem {
  subject_id: string;
  sex: "F" | "M" | "X" | "unknown";
  shotgun_count: number;
  amplicon_count: number;
}

export interface SubjectsResponse {
  total: number;
  page: number;
  pages: number;
  items: SubjectListItem[];
}

export interface GetSubjectsParams {
  page?: number;
  search?: string;
}

export async function getSubjects({
  page = 1,
  search = "",
}: GetSubjectsParams = {}): Promise<SubjectsResponse> {
  const res = await client.get<SubjectsResponse>("/subjects", {
    params: { page, search },
  });
  return res.data;
}

export async function getSubject(subjectId: string): Promise<Subject> {
  const res = await client.get<Subject>(`/subjects/${subjectId}`);
  return res.data;
}

export async function getSubjectCases(subjectId: string): Promise<CaseListItem[]> {
  const res = await client.get<CaseListItem[]>(`/subjects/${subjectId}/cases`);
  return res.data;
}
