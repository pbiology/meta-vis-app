import type { Case } from "../../../api/types";

interface PipelineConfig {
  pipeline_name?: string;
  pipeline_version?: string;
  nextflow?: string;
  [key: string]: unknown;
}

interface PipelineInfoShape {
  pipeline_configuration?: PipelineConfig;
  software_used?: Record<string, Record<string, unknown>>;
}

interface CaseProvenanceProps {
  caseData: Case;
}

function tools(info: PipelineInfoShape | undefined): Array<[string, string]> {
  const map: Record<string, string> = {};
  Object.values(info?.software_used ?? {}).forEach((processTools) => {
    Object.entries(processTools).forEach(([name, ver]) => {
      map[String(name)] = String(ver);
    });
  });
  return Object.entries(map).sort(([a], [b]) => a.localeCompare(b));
}

function PipelineBlock({
  config,
  toolRows,
}: {
  config: PipelineConfig;
  toolRows: Array<[string, string]>;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-6">
        {config.pipeline_name ? (
          <span className="text-xs text-gray-500">
            <span className="text-gray-400">{String(config.pipeline_name)}</span>
            <span className="font-mono ml-2 text-gray-700">{String(config.pipeline_version)}</span>
          </span>
        ) : null}
        {config.nextflow ? (
          <span className="text-xs text-gray-500">
            <span className="text-gray-400">Nextflow</span>
            <span className="font-mono ml-2 text-gray-700">{String(config.nextflow)}</span>
          </span>
        ) : null}
      </div>
      <table className="w-full">
        <thead>
          <tr>
            <th className="text-left text-[10px] font-semibold uppercase tracking-wider text-gray-400 pb-1.5 w-1/2">
              Tool
            </th>
            <th className="text-left text-[10px] font-semibold uppercase tracking-wider text-gray-400 pb-1.5">
              Version
            </th>
          </tr>
        </thead>
        <tbody>
          {toolRows.map(([name, ver]) => (
            <tr key={name} className="border-t border-gray-50">
              <td className="py-1 text-xs text-gray-600">{name}</td>
              <td className="py-1 font-mono text-xs text-gray-400">{ver}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function CaseProvenance({ caseData }: CaseProvenanceProps) {
  const info = caseData.pipeline_info as PipelineInfoShape | undefined;
  const mvInfo = caseData.metaval_pipeline_info as PipelineInfoShape | undefined;

  if (!info) {
    return (
      <section className="bg-white border border-gray-100 rounded-lg p-8 text-center text-sm text-gray-400">
        No pipeline provenance recorded for this case.
      </section>
    );
  }

  const config = info.pipeline_configuration ?? {};
  const toolRows = tools(info);
  const mvConfig = mvInfo?.pipeline_configuration ?? {};
  const mvToolRows = tools(mvInfo);

  return (
    <section className="bg-white border border-gray-100 rounded-lg p-5 flex flex-col gap-4">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900 m-0">
        Provenance
      </h3>
      <PipelineBlock config={config} toolRows={toolRows} />
      {mvInfo && mvToolRows.length > 0 && (
        <div className="border-t border-gray-50 pt-4">
          <PipelineBlock config={mvConfig} toolRows={mvToolRows} />
        </div>
      )}
    </section>
  );
}
