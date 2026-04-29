import { useEffect } from "react";
import Report from "./Report";
import { useReportData } from "./useReportData";

interface ReportPreviewModalProps {
  sampleId: string;
  taxonIds: number[];
  onClose: () => void;
}

export default function ReportPreviewModal({
  sampleId,
  taxonIds,
  onClose,
}: Readonly<ReportPreviewModalProps>) {
  const { data, isLoading, isError } = useReportData(sampleId, taxonIds);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 bg-black/30 flex items-stretch justify-center overflow-y-auto py-6">
      <div className="bg-white rounded-xl border border-gray-100 shadow-lg w-[840px] max-w-[95vw] flex flex-col">
        <div className="no-print flex items-center justify-between px-4 py-2.5 border-b border-gray-100">
          <p className="text-sm font-medium text-gray-700">Report preview</p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => globalThis.print()}
              disabled={!data}
              className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              Print / Save PDF
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close preview"
              className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
          {isLoading && <p className="text-xs text-gray-500 py-4 text-center">Loading…</p>}
          {isError && (
            <p className="text-xs text-red-600 py-4 text-center">Failed to assemble report data.</p>
          )}
          {data && <Report data={data} />}
        </div>
      </div>
    </div>
  );
}
