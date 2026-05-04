import { useState } from "react";
import { getCaseMultiQCUrl } from "../../../api/cases";

interface CaseMultiQCProps {
  caseId: string;
  available: boolean;
}

export default function CaseMultiQC({ caseId, available }: Readonly<CaseMultiQCProps>) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [errored, setErrored] = useState(false);

  if (!available) {
    return (
      <section className="bg-white border border-gray-100 rounded-lg p-8 text-center text-sm text-gray-400">
        No MultiQC report uploaded for this case.
      </section>
    );
  }

  async function load(): Promise<string | null> {
    if (url) return url;
    setLoading(true);
    setErrored(false);
    try {
      const fresh = await getCaseMultiQCUrl(caseId);
      setUrl(fresh);
      return fresh;
    } catch {
      setErrored(true);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function handleOpen() {
    const target = await load();
    if (target) window.open(target, "_blank");
  }

  async function handleDownload() {
    const target = await load();
    if (!target) return;
    const a = document.createElement("a");
    a.href = target;
    a.download = `multiqc_${caseId}.html`;
    a.click();
  }

  return (
    <section className="bg-white border border-gray-100 rounded-lg p-5 flex items-center gap-4">
      <div className="flex-1">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900 m-0">
          MultiQC report
        </h3>
        <p className="text-xs text-gray-500 mt-1 m-0">
          Aggregated QC metrics across all samples in this case.
        </p>
        {errored && <p className="text-xs text-red-500 mt-1">Failed to load report.</p>}
      </div>
      <button
        onClick={handleOpen}
        disabled={loading}
        className="px-3 py-1.5 text-xs rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
      >
        {loading ? "Loading…" : "Open in new tab"}
      </button>
      <button
        onClick={handleDownload}
        disabled={loading}
        className="px-3 py-1.5 text-xs rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
      >
        Download
      </button>
    </section>
  );
}
