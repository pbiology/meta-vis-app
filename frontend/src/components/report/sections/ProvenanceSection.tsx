import SectionHeading from "./SectionHeading";
import type { PipelineConfig } from "../useReportData";

interface ProvenanceSectionProps {
  taxprofilerInfo: PipelineConfig | undefined;
  metavalInfo: PipelineConfig | undefined;
}

const DASH = "—";

interface PipelineColumnProps {
  title: string;
  info: PipelineConfig | undefined;
}

function PipelineColumn({ title, info }: Readonly<PipelineColumnProps>) {
  const rows: Array<{ label: string; value: string | undefined }> = [
    { label: "Pipeline", value: info?.pipeline_name },
    { label: "Version", value: info?.pipeline_version },
    { label: "Nextflow", value: info?.nextflow },
  ];

  return (
    <div>
      <p className="report-provenance-col-label">{title}</p>
      <dl className="report-provenance-col">
        {rows.map(({ label, value }) => (
          <div key={label} className="report-kv-row">
            <dt className="report-kv-label">{label}</dt>
            <dd className="report-kv-value report-mono">{value ?? DASH}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default function ProvenanceSection({
  taxprofilerInfo,
  metavalInfo,
}: Readonly<ProvenanceSectionProps>) {
  return (
    <div className="report-page-break">
      <section className="report-section">
        <SectionHeading number={6} title="Provenance" />
        <div className="report-two-col">
          <PipelineColumn title="taxprofiler" info={taxprofilerInfo} />
          <PipelineColumn title="metaval" info={metavalInfo} />
        </div>
      </section>
    </div>
  );
}
