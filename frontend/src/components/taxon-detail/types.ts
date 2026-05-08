// Shapes returned by the taxa endpoints, narrowed locally for the UI.

export interface TaxonDoc {
  taxon_id: number;
  name?: string;
  rank?: string;
  species?: string;
  genus?: string;
  family?: string;
  order?: string;
  class?: string;
  phylum?: string;
  kingdom?: string;
  superkingdom?: string;
  ncbi_url?: string;
  clinical_notes?: string | null;
  clinical_notes_author?: string | null;
  clinical_notes_updated_at?: string | null;
  needs_taxonomy_refresh?: boolean;
  taxdump_version?: string;
  [key: string]: unknown;
}

export interface OccurrenceSample {
  sample_id: string;
  reads?: Record<string, number | null | undefined>;
}

export interface OccurrenceCase {
  case_id: string;
  order_date?: string | null;
  sample_count: number;
  classifiers?: string[];
  samples: OccurrenceSample[];
}

export interface OccurrencesData {
  total_cases: number;
  all_classifiers?: string[];
  cases: OccurrenceCase[];
}

export interface ExternalLink {
  name: string;
  url: string;
}

export interface LiteratureArticle {
  pmid: string | number;
  title: string;
  journal?: string;
  pub_date?: string;
  link: string;
}

export interface IsolationSource {
  source: string;
  count: number;
}

export interface CountryCount {
  country: string;
  count: number;
}

export interface AmrPhenotypeGenome {
  antibiotic: string;
  count: number;
}

export interface GenomesData {
  total_genomes: number;
  bvbrc_url: string;
  isolation_sources: IsolationSource[];
  countries: CountryCount[];
  amr_phenotypes: AmrPhenotypeGenome[];
}

export interface AmrGene {
  gene?: string;
  antibiotics?: string[];
  antibiotics_class?: string;
  source?: string;
  pmid?: (string | number)[];
}

export interface VirulenceFactor {
  gene?: string;
  product?: string;
  source?: string;
  pmid?: (string | number)[];
}

export interface AmrPhenotype {
  antibiotic: string;
  resistant: number;
  susceptible: number;
}

export interface SpecialtyData {
  amr_genes: AmrGene[];
  virulence_factors: VirulenceFactor[];
  amr_phenotypes: AmrPhenotype[];
  bvbrc_url?: string;
}

export const KINGDOM_COLOURS: Record<string, string> = {
  Viruses: "text-red-600",
  Bacteria: "text-blue-600",
  Eukaryota: "text-amber-600",
  Archaea: "text-purple-600",
};
