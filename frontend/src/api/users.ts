import client from "./client";
import type { MyStats, User, UserPreferences } from "./types";

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
