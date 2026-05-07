import KeyValueGrid, { type KvPair } from "./KeyValueGrid";
import SectionHeading from "./SectionHeading";
import type { PipelineConfig } from "../useReportData";

interface ProvenanceSectionProps {
  taxprofilerInfo: PipelineConfig | undefined;
  metavalInfo: PipelineConfig | undefined;
  generatedAt: string;
}

function pipelinePairs(info: PipelineConfig | undefined, label: string): KvPair[] {
  if (!info) return [];
  return [
    { label: `${label} pipeline`, value: info.pipeline_name, mono: true },
    { label: `${label} version`, value: info.pipeline_version, mono: true },
    { label: "Nextflow", value: info.nextflow, mono: true },
  ];
}

export default function ProvenanceSection({
  taxprofilerInfo,
  metavalInfo,
  generatedAt,
}: Readonly<ProvenanceSectionProps>) {
  const pairs: KvPair[] = [
    ...pipelinePairs(taxprofilerInfo, "taxprofiler"),
    ...pipelinePairs(metavalInfo, "metaval"),
    { label: "Report generated", value: generatedAt, mono: true },
  ];

  return (
    <div className="report-page-break">
      <section className="report-section">
        <SectionHeading number={6} title="Provenance" />
        <KeyValueGrid pairs={pairs} />
      </section>
    </div>
  );
}
