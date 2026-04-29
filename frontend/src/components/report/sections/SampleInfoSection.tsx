import type { Sample } from "../../../api/types";
import KeyValueGrid, { type KvPair } from "./KeyValueGrid";
import SectionHeading from "./SectionHeading";

interface SampleInfoSectionProps {
  sample: Sample;
}

function read(sample: Sample, key: string): string | number | undefined {
  const v = (sample as Record<string, unknown>)[key];
  return typeof v === "string" || typeof v === "number" ? v : undefined;
}

function readNested(sample: Sample, path: string[]): string | number | undefined {
  let cursor: unknown = sample;
  for (const k of path) {
    if (!cursor || typeof cursor !== "object") return undefined;
    cursor = (cursor as Record<string, unknown>)[k];
  }
  return typeof cursor === "string" || typeof cursor === "number" ? cursor : undefined;
}

export default function SampleInfoSection({ sample }: Readonly<SampleInfoSectionProps>) {
  // Pull what's available; sections render `—` for absent fields. The shape
  // in the design doc is aspirational — current SampleResponse has only some.
  const fastp = (sample.taxprofiler as { fastp?: Record<string, number> } | undefined)?.fastp;

  const pairs: KvPair[] = [
    { label: "Sample ID", value: read(sample, "sample_id"), mono: true },
    { label: "Case ID", value: read(sample, "case_id"), mono: true },
    { label: "Sample type", value: read(sample, "sample_type") },
    { label: "Material", value: read(sample, "material") },
    { label: "Sample source", value: read(sample, "sample_source") },
    { label: "Order date", value: read(sample, "order_date") },
    { label: "Received at", value: read(sample, "received_at") },
    {
      label: "Sequencing platform",
      value: readNested(sample, ["sequencing", "platform"]) ?? read(sample, "sequencing_platform"),
    },
    { label: "Analysis type", value: read(sample, "analysis_type") },
    {
      label: "Total reads",
      value: fastp?.total_reads_before_filtering?.toLocaleString(),
      mono: true,
    },
    {
      label: "Passed filter",
      value: fastp?.passed_filter_reads?.toLocaleString(),
      mono: true,
    },
    {
      label: "Q20 rate",
      value:
        typeof fastp?.q20_rate === "number" ? `${(fastp.q20_rate * 100).toFixed(2)}%` : undefined,
      mono: true,
    },
    {
      label: "Q30 rate",
      value:
        typeof fastp?.q30_rate === "number" ? `${(fastp.q30_rate * 100).toFixed(2)}%` : undefined,
      mono: true,
    },
  ];

  return (
    <section className="report-section">
      <SectionHeading number={1} title="Sample information" />
      <KeyValueGrid pairs={pairs} />
    </section>
  );
}
