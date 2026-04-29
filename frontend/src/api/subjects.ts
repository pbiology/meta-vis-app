import client from "./client";

export interface Subject {
  subject_id: string;
  sex?: "F" | "M" | "X" | "unknown" | null;
  [key: string]: unknown;
}

export async function getSubject(subjectId: string): Promise<Subject> {
  const res = await client.get<Subject>(`/subjects/${subjectId}`);
  return res.data;
}
