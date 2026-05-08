import { useQuery } from "@tanstack/react-query";
import { getSubject } from "../../api/subjects";

export const subjectKeys = {
  all: ["subjects"] as const,
  detail: (subjectId: string) => ["subjects", "detail", subjectId] as const,
};

export function useSubject(subjectId: string) {
  return useQuery({
    queryKey: subjectKeys.detail(subjectId),
    queryFn: () => getSubject(subjectId),
    enabled: Boolean(subjectId),
  });
}
