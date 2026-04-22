import client from "./client";
import type { Role, User, UserPreferences } from "./types";

export async function getUsers(): Promise<User[]> {
  const res = await client.get<User[]>("/users");
  return res.data;
}

export async function createUser(username: string, password: string, role: Role): Promise<unknown> {
  const res = await client.post("/users", { username, password, role });
  return res.data;
}

export async function updateUserRole(username: string, role: Role): Promise<unknown> {
  const res = await client.patch(`/users/${username}/role`, { role });
  return res.data;
}

export async function updateUserPassword(username: string, password: string): Promise<unknown> {
  const res = await client.patch(`/users/${username}/password`, { password });
  return res.data;
}

export async function deleteUser(username: string): Promise<unknown> {
  const res = await client.delete(`/users/${username}`);
  return res.data;
}

export async function getMyStats(): Promise<unknown> {
  const res = await client.get("/users/me/stats");
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
