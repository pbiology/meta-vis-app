import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createUser,
  deleteUser,
  getMyPreferences,
  getMyStats,
  getUsers,
  updateMyPreferences,
  updateUserPassword,
  updateUserRole,
} from "../../api/users";
import type { Role, UserPreferences } from "../../api/types";

export const userKeys = {
  all: ["users"] as const,
  list: () => ["users", "list"] as const,
  myStats: () => ["users", "me", "stats"] as const,
  myPreferences: () => ["users", "me", "preferences"] as const,
};

export function useUsers() {
  return useQuery({
    queryKey: userKeys.list(),
    queryFn: () => getUsers(),
  });
}

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

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      username,
      password,
      role,
    }: {
      username: string;
      password: string;
      role: Role;
    }) => createUser(username, password, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.list() }),
  });
}

export function useUpdateUserRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ username, role }: { username: string; role: Role }) =>
      updateUserRole(username, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.list() }),
  });
}

export function useUpdateUserPassword() {
  return useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      updateUserPassword(username, password),
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (username: string) => deleteUser(username),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.list() }),
  });
}

export function useUpdateMyPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (prefs: Partial<UserPreferences>) => updateMyPreferences(prefs),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.myPreferences() }),
  });
}
