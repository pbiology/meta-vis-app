import KeyValueGrid, { type KvPair } from "./KeyValueGrid";
import SectionHeading from "./SectionHeading";

interface ProvenanceSectionProps {
  pipelineInfo: unknown;
  generatedAt: string;
}

function pickString(obj: unknown, key: string): string | undefined {
  if (!obj || typeof obj !== "object") return undefined;
  const v = (obj as Record<string, unknown>)[key];
  return typeof v === "string" ? v : undefined;
}

function pickStringMap(obj: unknown, key: string): Record<string, string> | undefined {
  if (!obj || typeof obj !== "object") return undefined;
  const v = (obj as Record<string, unknown>)[key];
  if (!v || typeof v !== "object") return undefined;
  const out: Record<string, string> = {};
  for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
    if (typeof val === "string") out[k] = val;
  }
  return Object.keys(out).length > 0 ? out : undefined;
}

export default function ProvenanceSection({
  pipelineInfo,
  generatedAt,
}: Readonly<ProvenanceSectionProps>) {
  // PipelineInfoOutput in the backend is a permissive document. We pull a few
  // common fields and render the rest as a tools table when present.
  const pipelineName =
    pickString(pipelineInfo, "pipeline_name") ?? pickString(pipelineInfo, "name");
  const pipelineVersion =
    pickString(pipelineInfo, "pipeline_version") ?? pickString(pipelineInfo, "version");
  const nextflow = pickString(pipelineInfo, "nextflow_version");
  const tools =
    pickStringMap(pipelineInfo, "tools") ?? pickStringMap(pipelineInfo, "tool_versions");

  const pairs: KvPair[] = [
    { label: "Pipeline", value: pipelineName, mono: true },
    { label: "Pipeline version", value: pipelineVersion, mono: true },
    { label: "Nextflow", value: nextflow, mono: true },
    { label: "Report generated", value: generatedAt, mono: true },
  ];

  return (
    <div className="report-page-break">
      <section className="report-section">
        <SectionHeading number={5} title="Provenance" />
        <KeyValueGrid pairs={pairs} />
        {tools && (
          <table className="report-tools">
            <thead>
              <tr>
                <th>Tool</th>
                <th>Version</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(tools)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([name, version]) => (
                  <tr key={name}>
                    <td className="report-mono">{name}</td>
                    <td className="report-mono">{version}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
