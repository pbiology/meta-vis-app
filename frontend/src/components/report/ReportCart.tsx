import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getProfile } from "../../api/samples";
import { useReportBuilder } from "../../context/ReportBuilderContext";
import ReportPreviewModal from "./ReportPreviewModal";

interface CartTaxonInfo {
  name: string;
  rank?: string;
}

interface ReportCartProps {
  sampleId: string;
}

export default function ReportCart({ sampleId }: Readonly<ReportCartProps>) {
  const { data: profileData } = useQuery({
    queryKey: ["profile", sampleId],
    queryFn: () => getProfile(sampleId),
    staleTime: Infinity,
  });
  const taxonLookup = new Map<number, CartTaxonInfo>();
  for (const clf of profileData?.profiles ?? []) {
    for (const e of clf.profile ?? []) {
      if (!taxonLookup.has(e.taxon_id)) {
        taxonLookup.set(e.taxon_id, { name: e.name, rank: e.rank });
      }
    }
  }
  const { selectedFor, removeTaxon, clear } = useReportBuilder();
  const ids = selectedFor(sampleId);
  const [open, setOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Collapse the popover when the cart empties — nothing left to show.
  useEffect(() => {
    if (ids.length === 0) setOpen(false);
  }, [ids.length]);

  useEffect(() => {
    if (!open) return;
    function onMouseDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (ids.length === 0) return null;

  return (
    <div ref={containerRef} className="fixed bottom-6 right-6 z-30">
      {open && (
        <div
          aria-label="Report items"
          className="absolute bottom-full right-0 mb-2 w-[320px] max-h-[50vh] bg-white border border-gray-200 rounded-lg shadow-lg flex flex-col overflow-hidden"
        >
          <header className="px-4 py-2.5 border-b border-gray-100 flex items-center justify-between">
            <p className="text-xs font-medium text-gray-700">
              {ids.length} {ids.length === 1 ? "taxon" : "taxa"} in report
            </p>
            <button
              type="button"
              onClick={() => clear(sampleId)}
              className="text-xs text-gray-500 hover:text-red-600 transition-colors"
            >
              Clear all
            </button>
          </header>

          <ul className="flex-1 overflow-y-auto divide-y divide-gray-50">
            {ids.map((id) => {
              const info = taxonLookup.get(id);
              return (
                <li key={id} className="px-4 py-2 flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs italic text-gray-700 truncate">
                      {info?.name ?? `Taxon ${id}`}
                    </p>
                    {info?.rank && <p className="text-[11px] text-gray-400">{info.rank}</p>}
                  </div>
                  <button
                    type="button"
                    aria-label={`Remove ${info?.name ?? id} from report`}
                    onClick={() => removeTaxon(sampleId, id)}
                    className="text-gray-400 hover:text-red-600 text-base leading-none px-1"
                  >
                    ×
                  </button>
                </li>
              );
            })}
          </ul>

          <footer className="px-4 py-2.5 border-t border-gray-100">
            <button
              type="button"
              onClick={() => {
                setPreviewOpen(true);
                setOpen(false);
              }}
              className="w-full text-xs px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
            >
              Preview report
            </button>
          </footer>
        </div>
      )}

      <button
        type="button"
        aria-label="Report cart"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-4 py-2 rounded-full bg-blue-600 text-white shadow-lg hover:bg-blue-700 transition-colors text-xs font-medium"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" aria-hidden="true">
          <path
            d="M2.5 3h2l1.2 7.2a1 1 0 0 0 1 .8h6.1a1 1 0 0 0 1-.78L14.5 5H5"
            stroke="currentColor"
            strokeWidth="1.3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="6.5" cy="13" r="1" fill="currentColor" />
          <circle cx="12" cy="13" r="1" fill="currentColor" />
        </svg>
        Report · {ids.length}
      </button>
      {previewOpen && (
        <ReportPreviewModal
          sampleId={sampleId}
          taxonIds={ids}
          onClose={() => setPreviewOpen(false)}
        />
      )}
    </div>
  );
}
