import { useTaxon } from "../hooks/queries/useTaxa";
import { usePathogens } from "../hooks/queries/useAlerts";
import { useAuth } from "../context/AuthContext";
import { useReportBuilder } from "../context/ReportBuilderContext";
import LineageRow from "./taxon-detail/LineageRow";
import RefreshWarning from "./taxon-detail/RefreshWarning";
import ClinicalNotesEditor from "./taxon-detail/ClinicalNotesEditor";
import OccurrencesSection from "./taxon-detail/OccurrencesSection";
import ExternalLinksSection from "./taxon-detail/ExternalLinksSection";
import LiteratureSection from "./taxon-detail/LiteratureSection";
import BvbrcSection from "./taxon-detail/BvbrcSection";
import { KINGDOM_COLOURS, type TaxonDoc } from "./taxon-detail/types";

export interface TaxonDetailContentProps {
  taxonId: string;
  sampleId?: string;
  onBack: () => void;
}

export default function TaxonDetailContent({
  taxonId,
  sampleId,
  onBack,
}: Readonly<TaxonDetailContentProps>) {
  const { role } = useAuth();
  const { isSelected, addTaxon, removeTaxon } = useReportBuilder();

  const taxonQ = useTaxon(Number(taxonId));
  const taxon = taxonQ.data as TaxonDoc | undefined;

  const { data: pathogenList = [] } = usePathogens();

  const canEdit = role === "writer" || role === "admin";

  if (taxonQ.isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">Loading…</div>
    );
  }

  if (taxonQ.isError || !taxon) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <p className="text-sm text-gray-500">
          Taxon not found. Run load_taxonomy.py to populate reference data.
        </p>
        <button onClick={onBack} className="text-xs text-gray-400 hover:text-gray-600 underline">
          Go back
        </button>
      </div>
    );
  }

  const nameColour = (taxon.superkingdom && KINGDOM_COLOURS[taxon.superkingdom]) ?? "text-gray-900";
  const pathogen = pathogenList.find((p) => p.taxon_id === Number(taxonId));

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
        <h1 className={`text-sm font-medium italic flex-1 ${nameColour}`}>{taxon.name}</h1>
        <a
          href={taxon.ncbi_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-gray-400 hover:text-blue-500 font-mono transition-colors"
          title="Open in NCBI Taxonomy Browser"
        >
          taxid:{taxon.taxon_id}
        </a>
        {sampleId && canEdit && (
          <ReportToggleButton
            sampleId={sampleId}
            taxonId={taxon.taxon_id}
            isSelected={isSelected(sampleId, taxon.taxon_id)}
            onAdd={() => addTaxon(sampleId, taxon.taxon_id)}
            onRemove={() => removeTaxon(sampleId, taxon.taxon_id)}
          />
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-5">
        {taxon.needs_taxonomy_refresh && <RefreshWarning />}

        {pathogen && (
          <div className="flex items-start gap-2.5 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">
            <svg className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.3" />
              <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.3" />
              <path
                d="M8 2.5v1.5M8 12v1.5M2.5 8h1.5M12 8h1.5"
                stroke="currentColor"
                strokeWidth="1.3"
                strokeLinecap="round"
              />
            </svg>
            <span>
              <span className="font-medium">Known pathogen.</span>
              {pathogen.reason && <> {pathogen.reason}</>}
            </span>
          </div>
        )}

        <section className="bg-white border border-gray-100 rounded-xl p-4">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
            Taxonomy
          </p>
          <div className="grid grid-cols-2 gap-x-8">
            <div>
              <LineageRow label="Rank" value={taxon.rank} />
              <LineageRow label="Species" value={taxon.species} />
              <LineageRow label="Genus" value={taxon.genus} />
              <LineageRow label="Family" value={taxon.family} />
              <LineageRow label="Order" value={taxon.order} />
            </div>
            <div>
              <LineageRow label="Class" value={taxon.class} />
              <LineageRow label="Phylum" value={taxon.phylum} />
              <LineageRow label="Kingdom" value={taxon.kingdom} />
              <LineageRow label="Superkingdom" value={taxon.superkingdom} />
            </div>
          </div>
          {taxon.taxdump_version && (
            <p className="text-xs text-gray-300 mt-3">
              Taxonomy loaded from NCBI dump dated {taxon.taxdump_version}
            </p>
          )}
        </section>

        <ClinicalNotesEditor
          taxonId={taxon.taxon_id}
          initialNotes={taxon.clinical_notes}
          notesAuthor={taxon.clinical_notes_author}
          notesUpdatedAt={taxon.clinical_notes_updated_at}
          canEdit={canEdit}
        />

        <ExternalLinksSection taxonId={taxon.taxon_id} />
        <BvbrcSection taxonId={taxon.taxon_id} />
        <LiteratureSection taxonId={taxon.taxon_id} />
        <OccurrencesSection taxonId={taxon.taxon_id} />
      </div>
    </div>
  );
}

interface ReportToggleButtonProps {
  sampleId: string;
  taxonId: number;
  isSelected: boolean;
  onAdd: () => void;
  onRemove: () => void;
}

function ReportToggleButton({ isSelected, onAdd, onRemove }: Readonly<ReportToggleButtonProps>) {
  return (
    <button
      onClick={() => (isSelected ? onRemove() : onAdd())}
      className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
        isSelected
          ? "border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100"
          : "border-gray-200 text-gray-500 hover:bg-gray-50"
      }`}
    >
      {isSelected ? "In report ✓" : "Add to report"}
    </button>
  );
}
