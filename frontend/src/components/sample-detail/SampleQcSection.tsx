import { MetricStrip } from "../MetricStrip";
import { fmt, fmtPct } from "../../utils/format";
import type { Bowtie2Stats, FastpStats, TranaQc } from "./types";

interface SampleQcSectionProps {
  isTrana: boolean;
  trana?: TranaQc;
  fp?: FastpStats;
  bt?: Bowtie2Stats;
}

export default function SampleQcSection({
  isTrana,
  trana,
  fp,
  bt,
}: Readonly<SampleQcSectionProps>) {
  return (
    <section>
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">QC metrics</p>
      {isTrana ? (
        <MetricStrip
          metrics={[
            {
              label: "Total reads",
              value: fmt(trana?.nanoplot_unprocessed?.number_of_reads),
              sub: "before processing",
            },
            {
              label: "Passed filter",
              value: fmt(trana?.nanoplot_processed?.number_of_reads),
              sub: "after processing",
            },
            {
              label: "Mean read length",
              value: trana?.nanoplot_processed?.mean_read_length?.toFixed(0) ?? "—",
              sub: "bp",
            },
            {
              label: "Mean quality",
              value: trana?.nanoplot_processed?.mean_read_quality?.toFixed(1) ?? "—",
              sub: "Q",
            },
            {
              label: "Read N50",
              value: fmt(trana?.nanoplot_processed?.read_length_n50),
              sub: "bp",
            },
          ]}
        />
      ) : (
        <MetricStrip
          metrics={[
            {
              label: "Total reads",
              value: fp ? fmt(fp.total_reads_before_filtering) : "—",
              sub: "before filtering",
            },
            {
              label: "Passed filter",
              value: fp ? fmt(fp.passed_filter_reads) : "—",
              sub:
                fp?.passed_filter_reads != null && fp.total_reads_before_filtering
                  ? `${fmtPct(
                      (fp.passed_filter_reads / fp.total_reads_before_filtering) * 100
                    )} of raw`
                  : "",
            },
            {
              label: "Host removed",
              value: bt ? fmtPct(bt.overall_alignment_rate) : "—",
              sub: "bowtie2",
            },
            {
              label: "Non-host reads",
              value: bt ? fmt(bt.aligned_none) : "—",
              sub: "bowtie2",
            },
            {
              label: "Q20 rate",
              value: fmtPct(fp?.q20_rate ? fp.q20_rate * 100 : null),
              sub: "fastp",
            },
            {
              label: "Q30 rate",
              value: fmtPct(fp?.q30_rate ? fp.q30_rate * 100 : null),
              sub: "fastp",
            },
          ]}
        />
      )}
    </section>
  );
}
