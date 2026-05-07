// Shared domain types for the api layer.
// Expanded incrementally as consumers adopt TS.
// Response shapes with unstable/permissive backends keep an index signature.

export type Role = "admin" | "writer" | "reader";

export interface User {
  username: string;
  role: Role;
}

export interface AdminUser extends User {
  _id: string;
  reviewer_title?: string | null;
  reviews?: number;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  username: string;
  role: Role;
}

export interface MyStats {
  total_reviews?: number;
  reviews?: number;
  reviewer_title?: string | null;
  [key: string]: unknown;
}

export interface Case {
  case_id: string;
  [key: string]: unknown;
}

export interface CaseNote {
  id: string;
  text: string;
  author: string;
  created_at: string;
}

export interface CaseReview {
  reviewed?: boolean;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  notes?: string | null;
  [key: string]: unknown;
}

export interface CaseListItem extends Case {
  analysis_type?: string;
  sample_count?: number;
  control_count?: number;
  sample_names?: string[];
  order_date?: string | null;
  sequencing_platform?: string;
  ticket_id?: string | null;
  ticket_url?: string | null;
  review?: CaseReview;
  notes?: CaseNote[];
  report_selections?: Record<string, number[]>;
}

export interface CasesResponse {
  items: CaseListItem[];
  total: number;
  pages: number;
  ticket_links_enabled?: boolean;
  [key: string]: unknown;
}

export interface CaseStats {
  [key: string]: number | string | boolean | null | undefined;
}

export interface Sample {
  _id?: string;
  sample_id: string;
  case_id?: string;
  [key: string]: unknown;
}

export interface SampleProfileEntry {
  taxon_id: number;
  name: string;
  rank?: string;
  superkingdom?: string | null;
  reads?: number;
  fraction?: number;
  abundance: number;
  [key: string]: unknown;
}

export interface SampleProfile {
  classifier: string;
  classifier_db?: string;
  profile: SampleProfileEntry[];
  unclassified_reads?: number;
  [key: string]: unknown;
}

export interface SampleProfileResponse {
  profiles: SampleProfile[];
  [key: string]: unknown;
}

export interface NtcProfileForClassifier {
  sample_id: string;
  classifiers?: Record<string, Record<number, number>>;
}

export interface NtcContaminantConfig {
  threshold?: number;
  eligible_ranks?: string[];
}

export interface NtcProfilesResponse {
  profiles: NtcProfileForClassifier[];
  contaminant_config?: NtcContaminantConfig | null;
  [key: string]: unknown;
}

export interface Taxon {
  taxon_id: number;
  name?: string;
  rank?: string;
  superkingdom?: string;
  [key: string]: unknown;
}

export interface TaxonListItem {
  taxon_id: number;
  taxon_name: string;
  superkingdom: string | null;
  added_by: string;
  added_at: string;
}

export interface IgnorelistItem extends TaxonListItem {
  reason: string | null;
}

export interface PathogenItem extends TaxonListItem {
  reason: string | null;
}

export interface NtcContaminantItem extends TaxonListItem {
  min_reads: number;
  notes: string | null;
}

export interface NtcContaminantAlert {
  taxon_id: number;
  taxon_name: string;
  case_count: number;
  min_reads: number;
}

export interface NtcContaminantAlertsResponse {
  contaminant_case_ids: string[];
  alerts?: NtcContaminantAlert[];
  [key: string]: unknown;
}

export interface NtcKingdomPoint {
  sample_id: string;
  order_date: string;
  Bacteria?: number;
  Viruses?: number;
  Eukaryota?: number;
  Archaea?: number;
  Other?: number;
  [key: string]: unknown;
}

export interface NtcReadCountPoint {
  sample_id: string;
  case_id?: string;
  order_date: string;
  classified_reads: number;
}

export interface NtcTaxonOccurrence {
  order_date: string;
  abundance: number;
  case_id?: string;
}

export interface NtcRecurringTaxon {
  taxon_id: number;
  taxon_name: string;
  case_count: number;
  occurrences: NtcTaxonOccurrence[];
}

export interface NtcTrendsResponse {
  total_ntcs: number;
  min_case_count: number;
  kingdom_breakdown: NtcKingdomPoint[];
  read_counts: NtcReadCountPoint[];
  recurring_taxa: NtcRecurringTaxon[];
  [key: string]: unknown;
}

export interface OutbreakCase {
  case_id: string;
  order_date?: string | null;
  [key: string]: unknown;
}

export interface Outbreak {
  taxon_id: number;
  taxon_name: string;
  config_name?: string;
  superkingdoms?: string[];
  case_ids: string[];
  cases: OutbreakCase[];
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
  pages?: number;
  [key: string]: unknown;
}

export interface UserPreferences {
  preferred_kingdoms: string[];
  visible_analysis_types: string[];
}

export interface AuthContextValue {
  user: string | null;
  role: Role;
  preferences: UserPreferences;
  preferencesLoaded: boolean;
  authLoading: boolean;
  sessionKingdoms: string[];
  setSessionKingdoms: (kingdoms: string[]) => void;
  login: (username: string, role: Role) => Promise<void>;
  logout: () => void;
  setPreferences: (prefs: Partial<UserPreferences>) => Promise<void>;
}

// Metaval

export interface BlastHit {
  [key: string]: unknown;
}

export interface MetavalResult {
  _id: string;
  sample_id: string;
  organism_name?: string;
  verification_data?: Record<string, unknown>;
  blastn?: BlastHit[];
  blastx?: BlastHit[];
  [key: string]: unknown;
}

// Taxa detail payloads — permissive; pages narrow per-field.

export interface TaxonOccurrences {
  [key: string]: unknown;
}
export interface TaxonExternalLinks {
  [key: string]: unknown;
}
export interface TaxonLiterature {
  [key: string]: unknown;
}
export interface BvbrcGenomesResponse {
  [key: string]: unknown;
}
export interface BvbrcSpecialtyGenesResponse {
  [key: string]: unknown;
}

// NCBI lookup (shared by KnownPathogens + NtcListsPage)

export interface NcbiTaxonResult {
  scientificname: string;
  lineage?: string;
  genbankdivision?: string;
  status?: string;
}

export interface NcbiEsummaryResponse {
  result?: Record<string, NcbiTaxonResult | string[]>;
}
