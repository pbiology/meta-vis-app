import { useQuery } from "@tanstack/react-query";
import {
  getSubject,
  getSubjectCases,
  getSubjects,
  type GetSubjectsParams,
} from "../../api/subjects";

export const subjectKeys = {
  all: ["subjects"] as const,
  list: (params: GetSubjectsParams) => ["subjects", "list", params] as const,
  detail: (subjectId: string) => ["subjects", "detail", subjectId] as const,
  cases: (subjectId: string) => ["subjects", "cases", subjectId] as const,
};

interface PollOptions {
  refetchInterval?: number;
}

export function useSubjects(params: GetSubjectsParams = {}, opts: PollOptions = {}) {
  return useQuery({
    queryKey: subjectKeys.list(params),
    queryFn: () => getSubjects(params),
    refetchInterval: opts.refetchInterval,
  });
}

export function useSubject(subjectId: string) {
  return useQuery({
    queryKey: subjectKeys.detail(subjectId),
    queryFn: () => getSubject(subjectId),
    enabled: Boolean(subjectId),
  });
}

export function useSubjectCases(subjectId: string) {
  return useQuery({
    queryKey: subjectKeys.cases(subjectId),
    queryFn: () => getSubjectCases(subjectId),
    enabled: Boolean(subjectId),
  });
}
