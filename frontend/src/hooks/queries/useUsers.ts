import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getMyPreferences, getMyStats, updateMyPreferences } from "../../api/users";
import type { UserPreferences } from "../../api/types";

export const userKeys = {
  all: ["users"] as const,
  myStats: () => ["users", "me", "stats"] as const,
  myPreferences: () => ["users", "me", "preferences"] as const,
};

export function useMyStats() {
  return useQuery({
    queryKey: userKeys.myStats(),
    queryFn: () => getMyStats(),
  });
}

export function useMyPreferences() {
  return useQuery({
    queryKey: userKeys.myPreferences(),
    queryFn: () => getMyPreferences(),
  });
}

export function useUpdateMyPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (prefs: Partial<UserPreferences>) => updateMyPreferences(prefs),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.myPreferences() }),
  });
}
