import type { Sample } from "../api/types";

export interface TaxprofilerQcSummary {
  pipeline: "taxprofiler";
  rawReads: number | null;
  passedReads: number | null;
  // Share of raw reads that passed fastp filtering, 0–100.
  passedPct: number | null;
  // bowtie2 overall alignment rate against the host genome, 0–100. Not the
  // per-classifier host_pct the samples endpoint serves: that one divides
  // human reads by classified reads.
  hostPct: number | null;
  nonHostReads: number | null;
  q20Pct: number | null;
  q30Pct: number | null;
}

export interface TranaQcSummary {
  pipeline: "trana";
  rawReads: number | null;
  passedReads: number | null;
  meanLength: number | null;
  meanQuality: number | null;
  n50: number | null;
}

export type SampleQcSummary = TaxprofilerQcSummary | TranaQcSummary;

type QcSource = Pick<Sample, "taxprofiler" | "trana">;

/**
 * The QC numbers shown for a sample, from whichever pipeline produced it.
 *
 * The case sample table and the sample page both read these values from here,
 * so the two views cannot drift apart. A missing field is null rather than 0:
 * zero is a real result (e.g. a Q30 rate of 0), missing is not.
 *
 * `rawReads` reads the same fields as app/sample_read_deltas.py::read_count.
 * Where the samples endpoint serves `total_reads`, prefer that value.
 */
export function sampleQc(sample: QcSource | undefined): SampleQcSummary | null {
  if (sample?.trana) {
    const processed = sample.trana.nanoplot_processed;
    return {
      pipeline: "trana",
      rawReads: sample.trana.nanoplot_unprocessed?.number_of_reads ?? null,
      passedReads: processed?.number_of_reads ?? null,
      meanLength: processed?.mean_read_length ?? null,
      meanQuality: processed?.mean_read_quality ?? null,
      n50: processed?.read_length_n50 ?? null,
    };
  }
  if (sample?.taxprofiler) {
    const fp = sample.taxprofiler.fastp;
    const bt = sample.taxprofiler.bowtie2;
    const raw = fp?.total_reads_before_filtering ?? null;
    const passed = fp?.passed_filter_reads ?? null;
    return {
      pipeline: "taxprofiler",
      rawReads: raw,
      passedReads: passed,
      passedPct: passed != null && raw ? (passed / raw) * 100 : null,
      hostPct: bt?.overall_alignment_rate ?? null,
      nonHostReads: bt?.aligned_none ?? null,
      q20Pct: fp?.q20_rate == null ? null : fp.q20_rate * 100,
      q30Pct: fp?.q30_rate == null ? null : fp.q30_rate * 100,
    };
  }
  return null;
}
