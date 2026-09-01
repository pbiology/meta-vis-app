// Shared domain types for the api layer.
// Expanded incrementally as consumers adopt TS.
// Response shapes with unstable/permissive backends keep an index signature.

export type Role = "admin" | "writer" | "reader";

export interface User {
  username: string;
  role: Role;
}

export interface MyStats {
  total_reviews?: number;
  reviews?: number;
  reviewer_title?: string | null;
  [key: string]: unknown;
}

/**
 * Clinical identity of a case. Everything a pipeline run produces lives on
 * CaseAnalysis instead — a case may have been sequenced several times.
 */
export interface Case {
  case_id: string;
  ticket_id?: string | null;
  ticket_url?: string | null;
  order_date?: string | null;
  created_at?: string | null;
  subject_id?: string | null;
  notes?: CaseNote[];
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

export interface CaseClassifier {
  name: string;
  db: string;
  krona_id?: string | null;
}

/** Slim per-run summary — backs the version switcher and the collapsed rows. */
export interface AnalysisSummary {
  case_id: string;
  version: number;
  is_latest: boolean;
  order_date?: string | null;
  ingested_at?: string | null;
  analysis_type?: string | null;
  sequencing_platform?: string | null;
  review?: CaseReview;
  sample_count?: number;
  control_count?: number;
}

/** One pipeline run of a case. */
export interface CaseAnalysis extends AnalysisSummary {
  classifiers?: CaseClassifier[];
  has_krona?: boolean;
  has_multiqc?: boolean;
  pipeline_info?: unknown;
  metaval_pipeline_info?: unknown;
  report_selections?: Record<string, number[]>;
  sample_names?: string[];
  [key: string]: unknown;
}

/** One row of the case list: a case plus its latest run, older runs nested. */
export interface CaseListItem {
  case: Case;
  latest: AnalysisSummary;
  superseded_analyses: AnalysisSummary[];
}

/** GET /cases/{case_id} — identity, the run being viewed, and every run. */
export interface CaseDetail {
  case: Case;
  analysis: CaseAnalysis | null;
  analyses: AnalysisSummary[];
}

/**
 * A case flattened together with one of its analyses.
 *
 * The report and the case view present a case *at* a particular run, reading
 * identity fields (case_id, ticket, subject) and run fields (classifiers,
 * pipeline info, review) side by side. Merging them once here keeps those
 * consumers from having to know which document each field came from.
 */
export type CaseAtAnalysis = Case & Partial<CaseAnalysis>;

/** Flatten a detail response into the merged view model. */
export function flattenCaseDetail(detail: CaseDetail): CaseAtAnalysis {
  return { ...(detail.analysis ?? {}), ...detail.case };
}

export interface CasesResponse {
  items: CaseListItem[];
  total: number;
  pages: number;
  ticket_links_enabled?: boolean;
  [key: string]: unknown;
}

export interface CaseStats {
  total?: number;
  pending?: number;
  reviewed?: number;
  pending_shotgun?: number;
  pending_amplicon?: number;
  [key: string]: number | string | boolean | null | undefined;
}

export interface Sample {
  _id?: string;
  sample_id: string;
  case_id?: string;
  // True when a metaval analysis was ingested for the parent case. Derived
  // server-side; lets the UI tell "no metaval run" from "metaval run, no hits".
  has_metaval?: boolean;
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
  login: () => Promise<void>;
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
