// Inner shapes of Sample.taxprofiler / Sample.trana sub-objects, narrowed
// locally for the sample-detail UI.

export interface NanoplotStats {
  number_of_reads?: number;
  mean_read_length?: number;
  mean_read_quality?: number;
  read_length_n50?: number;
}

export interface TranaQc {
  nanoplot_unprocessed?: NanoplotStats;
  nanoplot_processed?: NanoplotStats;
}

export interface FastpStats {
  total_reads_before_filtering?: number;
  passed_filter_reads?: number;
  q20_rate?: number;
  q30_rate?: number;
}

export interface Bowtie2Stats {
  overall_alignment_rate?: number;
  aligned_none?: number;
}

export interface ClassifierQcStats {
  unclassified_reads?: number;
  total_reads?: number;
  queries_aligned?: number;
  [key: string]: unknown;
}

export interface TaxprofilerQc {
  fastp?: FastpStats;
  bowtie2?: Bowtie2Stats;
  classifiers?: Record<string, ClassifierQcStats | undefined>;
}

export type SuperkingdomKey = "Bacteria" | "Eukaryota" | "Viruses" | "Archaea";
