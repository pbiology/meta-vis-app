import { fmt, fmtPct } from "../../../utils/format";
import type {
  SampleQcSummary,
  TaxprofilerQcSummary,
  TranaQcSummary,
} from "../../../utils/sampleQc";

export interface QcColumn {
  label: string;
  // Header tooltip saying where the number comes from.
  title: string;
  cell: (qc: SampleQcSummary | null) => string;
}

// A sample from another pipeline, or one without a QC block, shows a dash
// rather than a number that means something else.
const taxprofiler =
  (pick: (qc: TaxprofilerQcSummary) => string) =>
  (qc: SampleQcSummary | null): string =>
    qc?.pipeline === "taxprofiler" ? pick(qc) : "—";

const trana =
  (pick: (qc: TranaQcSummary) => string) =>
  (qc: SampleQcSummary | null): string =>
    qc?.pipeline === "trana" ? pick(qc) : "—";

const TAXPROFILER_COLUMNS: QcColumn[] = [
  {
    label: "Passed",
    title: "Share of raw reads passing fastp filtering",
    cell: taxprofiler((qc) => fmtPct(qc.passedPct)),
  },
  {
    label: "Host",
    title: "Reads removed as host (bowtie2)",
    cell: taxprofiler((qc) => fmtPct(qc.hostPct)),
  },
  {
    label: "Non-host reads",
    title: "Reads left after host removal (bowtie2)",
    cell: taxprofiler((qc) => fmt(qc.nonHostReads)),
  },
  {
    label: "Q30",
    title: "Share of bases at Q30 or above (fastp)",
    cell: taxprofiler((qc) => fmtPct(qc.q30Pct)),
  },
];

const TRANA_COLUMNS: QcColumn[] = [
  {
    label: "Passed",
    title: "Reads left after processing (NanoPlot)",
    cell: trana((qc) => fmt(qc.passedReads)),
  },
  {
    label: "Mean Q",
    title: "Mean read quality after processing (NanoPlot)",
    cell: trana((qc) => fmt(qc.meanQuality, 1)),
  },
  {
    label: "N50",
    title: "Read length N50 after processing, bp (NanoPlot)",
    cell: trana((qc) => fmt(qc.n50)),
  },
];

/**
 * The QC columns for a case's sample table.
 *
 * An analysis comes from one pipeline, so the first sample with a QC block
 * decides. No columns when no sample has one: a row of dashes says nothing.
 */
export function qcColumnsFor(summaries: readonly (SampleQcSummary | null)[]): QcColumn[] {
  const pipeline = summaries.find((qc) => qc !== null)?.pipeline;
  if (pipeline === "taxprofiler") return TAXPROFILER_COLUMNS;
  if (pipeline === "trana") return TRANA_COLUMNS;
  return [];
}
