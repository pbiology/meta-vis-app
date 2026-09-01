import { useEffect, useRef, useState } from "react";
import { useCaseMultiQCUrl } from "../../../hooks/queries/useCases";

interface CaseMultiQCProps {
  caseId: string;
  available: boolean;
  /** Analysis being viewed; null means the case's latest. */
  version: number | null;
}

export default function CaseMultiQC({ caseId, available, version }: Readonly<CaseMultiQCProps>) {
  // Each analysis has its own MultiQC report, so this must follow the run on
  // screen rather than defaulting to the latest.
  const { data: url, isLoading, isError } = useCaseMultiQCUrl(available ? caseId : "", version);
  const [iframeHeight, setIframeHeight] = useState<number>(600);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Blob URLs leak unless explicitly revoked. Tied to the data identity so the
  // URL is revoked exactly once when the component unmounts or the URL changes.
  useEffect(() => {
    if (!url) return;
    return () => URL.revokeObjectURL(url);
  }, [url]);

  if (!available) {
    return (
      <section className="bg-white border border-gray-100 rounded-lg p-8 text-center text-sm text-gray-400">
        No MultiQC report uploaded for this case.
      </section>
    );
  }

  function handleIframeLoad() {
    const doc = iframeRef.current?.contentDocument;
    if (doc) setIframeHeight(doc.documentElement.scrollHeight);
  }

  function handleDownload() {
    if (!url) return;
    const a = document.createElement("a");
    a.href = url;
    a.download = `multiqc_${caseId}.html`;
    a.click();
  }

  return (
    <section className="bg-white border border-gray-100 rounded-lg p-5 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900 m-0">
            MultiQC report
          </h3>
          <p className="text-xs text-gray-500 mt-1 m-0">
            Aggregated QC metrics across all samples in this case.
          </p>
          {isError && <p className="text-xs text-red-500 mt-1">Failed to load report.</p>}
        </div>
        <button
          onClick={handleDownload}
          disabled={!url}
          className="px-3 py-1.5 text-xs rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors shrink-0"
        >
          Download
        </button>
      </div>

      {isLoading && <div className="h-24 animate-pulse bg-gray-50 rounded" />}
      {url && !isLoading && (
        <iframe
          ref={iframeRef}
          src={url}
          title="MultiQC report"
          className="w-full rounded border border-gray-100"
          style={{ height: iframeHeight }}
          onLoad={handleIframeLoad}
          sandbox="allow-scripts allow-same-origin"
        />
      )}
    </section>
  );
}
