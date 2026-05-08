// Inner shapes of the MetavalResult document. The backend returns these as
// loosely-typed sub-objects, so we narrow them locally for the metaval UI.

export interface VerificationData {
  type?: string;
  count?: number;
  file_count?: number;
  avg_length?: number;
  available?: boolean;
}

export interface BlastHitRow {
  qseqid?: string;
  ssciname?: string;
  staxid?: string | number;
  organism_name?: string;
  median_pident?: string | number;
  median_length?: string | number;
  median_bitscore?: string | number;
  count?: number;
}

export interface BlastResults {
  blastn?: BlastHitRow[];
  blastx?: BlastHitRow[];
}

export interface CandidateOrganism {
  organism_name: string;
  igv_too_large?: boolean;
  igv_file_size_bytes?: number;
}
