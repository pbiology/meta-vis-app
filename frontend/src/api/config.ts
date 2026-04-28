import apiClient from "./client";

export interface AppConfig {
  host_taxon_ids: number[];
}

export async function fetchAppConfig(): Promise<AppConfig> {
  const res = await apiClient.get<AppConfig>("/config");
  return res.data;
}
