import { describe, it, expect } from "vitest";
import { sampleQc } from "./sampleQc";

describe("sampleQc", () => {
  it("summarises a taxprofiler sample from fastp and bowtie2", () => {
    const qc = sampleQc({
      taxprofiler: {
        fastp: {
          total_reads_before_filtering: 1_000,
          passed_filter_reads: 800,
          q20_rate: 0.97,
          q30_rate: 0.9,
        },
        bowtie2: { overall_alignment_rate: 40, aligned_none: 480 },
      },
    });

    expect(qc).toEqual({
      pipeline: "taxprofiler",
      rawReads: 1_000,
      passedReads: 800,
      passedPct: 80,
      hostPct: 40,
      nonHostReads: 480,
      q20Pct: 97,
      q30Pct: 90,
    });
  });

  it("keeps a Q30 rate of zero instead of treating it as missing", () => {
    const qc = sampleQc({ taxprofiler: { fastp: { q30_rate: 0 } } });

    expect(qc?.pipeline === "taxprofiler" && qc.q30Pct).toBe(0);
  });

  it("returns nulls for missing taxprofiler fields", () => {
    const qc = sampleQc({ taxprofiler: {} });

    expect(qc).toEqual({
      pipeline: "taxprofiler",
      rawReads: null,
      passedReads: null,
      passedPct: null,
      hostPct: null,
      nonHostReads: null,
      q20Pct: null,
      q30Pct: null,
    });
  });

  it("does not divide by a zero raw read count", () => {
    const qc = sampleQc({
      taxprofiler: { fastp: { total_reads_before_filtering: 0, passed_filter_reads: 0 } },
    });

    expect(qc?.pipeline === "taxprofiler" && qc.passedPct).toBeNull();
  });

  it("summarises a TRANA sample from the processed NanoPlot stats", () => {
    const qc = sampleQc({
      trana: {
        nanoplot_unprocessed: { number_of_reads: 5_000 },
        nanoplot_processed: {
          number_of_reads: 4_000,
          mean_read_length: 1_450,
          mean_read_quality: 14.2,
          read_length_n50: 1_500,
        },
      },
    });

    expect(qc).toEqual({
      pipeline: "trana",
      rawReads: 5_000,
      passedReads: 4_000,
      meanLength: 1_450,
      meanQuality: 14.2,
      n50: 1_500,
    });
  });

  it("returns null for a sample without a QC block", () => {
    expect(sampleQc({})).toBeNull();
    expect(sampleQc(undefined)).toBeNull();
  });
});
