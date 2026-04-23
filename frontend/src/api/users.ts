import client from "./client";
import type { AdminUser, MyStats, Role, User, UserPreferences } from "./types";

export async function getUsers(): Promise<AdminUser[]> {
  const res = await client.get<AdminUser[]>("/users");
  return res.data;
}

export async function createUser(
  username: string,
  password: string,
  role: Role
): Promise<AdminUser> {
  const res = await client.post<AdminUser>("/users", { username, password, role });
  return res.data;
}

export async function updateUserRole(username: string, role: Role): Promise<void> {
  await client.patch(`/users/${username}/role`, { role });
}

export async function updateUserPassword(username: string, password: string): Promise<void> {
  await client.patch(`/users/${username}/password`, { password });
}

export async function deleteUser(username: string): Promise<void> {
  await client.delete(`/users/${username}`);
}

export async function getMyStats(): Promise<MyStats> {
  const res = await client.get<MyStats>("/users/me/stats");
  return res.data;
}

export async function getMyPreferences(): Promise<UserPreferences> {
  const res = await client.get<UserPreferences>("/users/me/preferences");
  return res.data;
}

export async function updateMyPreferences(
  prefs: Partial<UserPreferences>
): Promise<UserPreferences> {
  const res = await client.patch<UserPreferences>("/users/me/preferences", prefs);
  return res.data;
}

export type { User };
