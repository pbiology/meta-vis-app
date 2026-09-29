import TaxonomyTable, { type TaxonomySelection } from "../TaxonomyTable";
import { useAppConfig } from "../../context/ConfigContext";
import { isListedTaxon } from "../../utils/taxonFilters";
import { metavalForClassifier, unmatchedMetaval } from "../../utils/metavalMatch";
import type { MetavalSummary, SampleProfile } from "../../api/types";
import type { ClassifierQcStats } from "./types";
import MetavalStatus from "./MetavalStatus";

interface NtcProfile {
  sample_id: string;
  classifiers?: Record<string, Record<number, number>>;
}

interface SampleTaxonomySectionProps {
  classifiers: SampleProfile[];
  qc: { classifiers?: Record<string, ClassifierQcStats | undefined> } | undefined;
  metavalResults: MetavalSummary[];
  hasMetavalAnalysis: boolean;
  // The caller shows its own load-failure warning; the metaval status line is
  // then suppressed, since an empty list would read as "nothing examined".
  metavalLoadFailed: boolean;
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
  onSelectMetaval: (metavalId: string) => void;
}

export default function SampleTaxonomySection({
  classifiers,
  qc,
  metavalResults,
  hasMetavalAnalysis,
  metavalLoadFailed,
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
  onSelectMetaval,
}: Readonly<SampleTaxonomySectionProps>) {
  const { hostTaxonIds } = useAppConfig();
  if (classifiers.length === 0) return null;

  const activeProfile = classifiers.find((clf) => clf.classifier === activeTab);
  // metaval runs on taxprofiler output only.
  const showMetavalStatus = !isTrana && !metavalLoadFailed && activeProfile !== undefined;
  const activeMetaval = activeProfile
    ? metavalForClassifier(metavalResults, activeProfile.classifier)
    : [];
  const listedTaxonIds = new Set(
    (activeProfile?.profile ?? [])
      .filter((t) => isListedTaxon(t, hostTaxonIds))
      .map((t) => t.taxon_id)
  );

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
      {showMetavalStatus && (
        <MetavalStatus
          hasMetavalAnalysis={hasMetavalAnalysis}
          classifier={activeProfile.classifier}
          results={activeMetaval}
          unmatched={unmatchedMetaval(activeMetaval, listedTaxonIds)}
          onSelectMetaval={onSelectMetaval}
        />
      )}
      {activeProfile && (
        <TaxonomyTable
          key={activeProfile.classifier}
          profile={activeProfile}
          allProfiles={classifiers}
          clfQc={qc?.classifiers?.[activeProfile.classifier]}
          metavalResults={metavalResults}
          sampleId={sampleId}
          outbreakTaxonIds={outbreakTaxonIds}
          ntcProfiles={ntcProfiles}
          contaminantConfig={contaminantConfig}
          pathogenIds={pathogenIds}
          abundanceIsFraction={isTrana}
          isNtc={sampleType !== "sample"}
          selection={selection}
          onSelectTaxon={onSelectTaxon}
          onSelectMetaval={onSelectMetaval}
        />
      )}
    </section>
  );
}
