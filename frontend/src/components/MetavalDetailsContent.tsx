import { useState } from "react";
import { useMetavalResult } from "../hooks/queries/useMetaval";
import TaxonDetailContent from "./TaxonDetailContent";
import MetavalVerificationDataSection from "./metaval/MetavalVerificationDataSection";
import MetavalBlastResultsSection from "./metaval/MetavalBlastResultsSection";
import MetavalCandidateOrganismsSection from "./metaval/MetavalCandidateOrganismsSection";
import type { BlastResults, CandidateOrganism } from "./metaval/types";

export interface MetavalDetailsContentProps {
  metavalId: string;
  onBack: () => void;
}

export default function MetavalDetailsContent({
  metavalId,
  onBack,
}: Readonly<MetavalDetailsContentProps>) {
  const { data: result, isLoading, isError } = useMetavalResult(metavalId);
  const [activeTaxonId, setActiveTaxonId] = useState<string | null>(null);

  if (activeTaxonId) {
    return <TaxonDetailContent taxonId={activeTaxonId} onBack={() => setActiveTaxonId(null)} />;
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">Loading…</div>
    );
  }
  if (isError || !result) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-red-500">
        Failed to load metaval result.
      </div>
    );
  }

  const taxonName = result.taxon_name as string | undefined;
  const taxonLabel = taxonName?.replace(/^taxid_\d+_/, "").replace(/-/g, " ") ?? "—";
  const sampleName = result.sample_name as string | undefined;
  const classifier = result.classifier as string | undefined;
  const taxonId = result.taxon_id as number | undefined;
  const blast = result.blast as BlastResults | undefined;
  const organisms = result.organisms as CandidateOrganism[] | undefined;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <button
          onClick={onBack}
          className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 transition-colors"
        >
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
            <path
              d="M10 3L5 8l5 5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Back
        </button>
        <span className="text-gray-200">/</span>
        <span className="text-xs text-gray-400 font-mono">{sampleName}</span>
        <span className="text-gray-200">/</span>
        <span className="text-xs text-gray-400">{classifier}</span>
        <span className="text-gray-200">/</span>
        <h1 className="text-sm font-medium text-gray-900 italic">{taxonLabel}</h1>
        {taxonId && (
          <a
            href={`https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=${taxonId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-1 text-xs text-gray-400 hover:text-blue-500 font-mono transition-colors"
            title="Open in NCBI Taxonomy Browser"
          >
            taxid:{taxonId}
          </a>
        )}
      </div>
      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-5">
        <MetavalVerificationDataSection metavalId={metavalId} result={result} />
        <MetavalBlastResultsSection blast={blast} onSelectTaxon={setActiveTaxonId} />
        <MetavalCandidateOrganismsSection metavalId={metavalId} organisms={organisms} />
      </div>
    </div>
  );
}
