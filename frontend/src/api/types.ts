// Shared domain types for the api layer.
// Intentionally minimal — expanded incrementally as consumers adopt TS.
// Unmodelled response shapes stay `unknown` until a caller needs more.

export type Role = "admin" | "writer" | "reader";

export interface User {
  username: string;
  role: Role;
}

export interface Case {
  _id?: string;
  case_id: string;
  [key: string]: unknown;
}

export interface Sample {
  _id?: string;
  sample_id: string;
  case_id?: string;
  [key: string]: unknown;
}

export interface Taxon {
  taxon_id: number;
  name?: string;
  rank?: string;
  superkingdom?: string;
  [key: string]: unknown;
}

export interface Outbreak {
  config_name?: string;
  superkingdoms?: string[];
  [key: string]: unknown;
}

export interface OutbreaksResponse {
  window_days: number;
  outbreaks: Outbreak[];
}

export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  total: number;
  [key: string]: unknown;
}
