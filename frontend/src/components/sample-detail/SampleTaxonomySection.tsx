import TaxonomyTable, { type TaxonomySelection } from "../TaxonomyTable";
import type { MetavalResult, SampleProfile } from "../../api/types";
import type { ClassifierQcStats } from "./types";

interface NtcProfile {
  sample_id: string;
  classifiers?: Record<string, Record<number, number>>;
}

interface SampleTaxonomySectionProps {
  classifiers: SampleProfile[];
  qc: { classifiers?: Record<string, ClassifierQcStats | undefined> } | undefined;
  metavalResults: MetavalResult[];
  sampleId: string;
  outbreakTaxonIds: Set<number>;
  ntcProfiles: NtcProfile[];
  contaminantConfig: { threshold?: number; eligible_ranks?: string[] } | null;
  pathogenIds: Set<number>;
  isTrana: boolean;
  sampleType: string;
  selection?: TaxonomySelection;
  activeTab: string | null;
  onTabChange: (classifier: string) => void;
  onSelectTaxon: (taxonId: number) => void;
}

export default function SampleTaxonomySection({
  classifiers,
  qc,
  metavalResults,
  sampleId,
  outbreakTaxonIds,
  ntcProfiles,
  contaminantConfig,
  pathogenIds,
  isTrana,
  sampleType,
  selection,
  activeTab,
  onTabChange,
  onSelectTaxon,
}: Readonly<SampleTaxonomySectionProps>) {
  if (classifiers.length === 0) return null;
  return (
    <section className="bg-white border border-gray-100 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">
          Taxonomy
        </p>
        <div className="flex gap-1.5">
          {classifiers.map((clf) => (
            <button
              key={clf.classifier}
              onClick={() => onTabChange(clf.classifier)}
              className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                activeTab === clf.classifier
                  ? "bg-gray-900 text-white font-medium"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              {clf.classifier}
            </button>
          ))}
        </div>
      </div>
      {activeTab &&
        classifiers.map((clf) =>
          clf.classifier === activeTab ? (
            <TaxonomyTable
              key={clf.classifier}
              profile={clf}
              allProfiles={classifiers}
              clfQc={qc?.classifiers?.[clf.classifier]}
              metavalResults={metavalResults.map((r) => {
                const rx = r as unknown as { taxon_id: number; classifier: string };
                return { _id: r._id, taxon_id: rx.taxon_id, classifier: rx.classifier };
              })}
              sampleId={sampleId}
              outbreakTaxonIds={outbreakTaxonIds}
              ntcProfiles={ntcProfiles}
              contaminantConfig={contaminantConfig}
              pathogenIds={pathogenIds}
              abundanceIsFraction={isTrana}
              isNtc={sampleType !== "sample"}
              selection={selection}
              onSelectTaxon={onSelectTaxon}
            />
          ) : null
        )}
    </section>
  );
}
