import type { AnalysisSummary, Sample } from "../../../api/types";
import { useReportBuilder } from "../../../context/ReportBuilderContext";
import Report from "../../report/Report";
import { useReportData } from "../../report/useReportData";
import ReportCarryForwardPrompt from "./ReportCarryForwardPrompt";

interface CaseReportSectionProps {
  caseId: string;
  samples: Sample[];
  /** Analysis being viewed; null means the case's latest. */
  version?: number | null;
  analyses?: AnalysisSummary[];
  canEdit?: boolean;
}

export default function CaseReportSection({
  caseId,
  samples,
  version = null,
  analyses = [],
  canEdit = false,
}: Readonly<CaseReportSectionProps>) {
  const { selectedFor } = useReportBuilder();

  const samplesWithSelections = samples.filter((s) => selectedFor(s.sample_id).length > 0);
  const totalCount = samplesWithSelections.reduce((n, s) => n + selectedFor(s.sample_id).length, 0);

  const selectionsBySampleId: Record<string, number[]> = {};
  for (const s of samplesWithSelections) {
    selectionsBySampleId[s.sample_id] = selectedFor(s.sample_id);
  }

  const { data, isLoading, isError } = useReportData(caseId, selectionsBySampleId, version);

  if (samplesWithSelections.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <ReportCarryForwardPrompt
          caseId={caseId}
          version={version}
          analyses={analyses}
          canEdit={canEdit}
        />
        <section className="bg-white border border-gray-100 rounded-lg p-10 text-center">
          <div className="text-sm font-semibold text-gray-700 mb-1">Report builder</div>
          <div className="text-xs text-gray-400">
            No taxa selected. Open a sample and tick taxa in the taxonomy table — or use “Add to
            report” on a taxon detail page — to add them here.
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="no-print bg-white border border-gray-100 rounded-lg px-5 py-3 flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-700 m-0">Report preview</p>
          <p className="text-xs text-gray-400 m-0 mt-0.5">
            {totalCount} {totalCount === 1 ? "taxon" : "taxa"} across {samplesWithSelections.length}{" "}
            {samplesWithSelections.length === 1 ? "sample" : "samples"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => globalThis.print()}
            className="text-xs px-3 py-1.5 rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Print / Save PDF
          </button>
          <button
            type="button"
            onClick={() => globalThis.print()}
            className="text-xs px-3 py-1.5 rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors"
          >
            Finalise report
          </button>
        </div>
      </header>

      <section className="bg-white border border-gray-100 rounded-lg p-4">
        {isLoading && <p className="text-xs text-gray-500 py-4 text-center m-0">Loading report…</p>}
        {isError && (
          <p className="text-xs text-red-600 py-4 text-center m-0">
            Failed to assemble case report data.
          </p>
        )}
        {data && <Report data={data} />}
      </section>
    </div>
  );
}
