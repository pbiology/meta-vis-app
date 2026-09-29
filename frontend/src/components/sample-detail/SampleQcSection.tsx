import { useState } from "react";
import { MetricStrip, type Metric } from "../MetricStrip";
import { fmt, fmtPct } from "../../utils/format";
import type { SampleQcSummary } from "../../utils/sampleQc";

interface SampleQcSectionProps {
  qc: SampleQcSummary | null;
}

function summaryParts(qc: SampleQcSummary): string[] {
  if (qc.pipeline === "trana") {
    return [
      `${fmt(qc.passedReads)} passed`,
      `mean Q ${fmt(qc.meanQuality, 1)}`,
      `N50 ${fmt(qc.n50)} bp`,
    ];
  }
  return [
    `${fmtPct(qc.passedPct)} passed`,
    `${fmtPct(qc.hostPct)} host`,
    `${fmt(qc.nonHostReads)} non-host`,
    `Q30 ${fmtPct(qc.q30Pct)}`,
  ];
}

function detailMetrics(qc: SampleQcSummary): Metric[] {
  const raw = { label: "Total reads", value: fmt(qc.rawReads), sub: "raw input" };
  if (qc.pipeline === "trana") {
    return [
      raw,
      { label: "Passed filter", value: fmt(qc.passedReads), sub: "after processing" },
      { label: "Mean read length", value: fmt(qc.meanLength), sub: "bp" },
      { label: "Mean quality", value: fmt(qc.meanQuality, 1), sub: "Q" },
      { label: "Read N50", value: fmt(qc.n50), sub: "bp" },
    ];
  }
  return [
    raw,
    {
      label: "Passed filter",
      value: fmt(qc.passedReads),
      sub: qc.passedPct == null ? "fastp" : `${fmtPct(qc.passedPct)} of raw`,
    },
    { label: "Host removed", value: fmtPct(qc.hostPct), sub: "bowtie2" },
    { label: "Non-host reads", value: fmt(qc.nonHostReads), sub: "bowtie2" },
    { label: "Q20 rate", value: fmtPct(qc.q20Pct), sub: "fastp" },
    { label: "Q30 rate", value: fmtPct(qc.q30Pct), sub: "fastp" },
  ];
}

/**
 * Sample QC as one line, with the full metrics one click away.
 *
 * Comparing QC across samples happens in the case's sample table; here it is
 * context for reading the taxonomy, so it stays compact.
 */
export default function SampleQcSection({ qc }: Readonly<SampleQcSectionProps>) {
  const [open, setOpen] = useState(false);

  return (
    <section>
      <div className="flex items-center gap-3">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">QC</p>
        <p className="text-xs text-gray-700 font-mono flex-1">
          {qc ? summaryParts(qc).join(" · ") : "No QC data for this sample."}
        </p>
        {qc && (
          <button
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="text-xs text-blue-600 hover:underline"
          >
            {open ? "Hide details" : "Details"}
          </button>
        )}
      </div>
      {qc && open && (
        <div className="mt-2">
          <MetricStrip metrics={detailMetrics(qc)} />
        </div>
      )}
    </section>
  );
}
