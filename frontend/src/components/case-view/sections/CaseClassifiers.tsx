import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Sample } from "../../../api/types";
import CaseClassifierTable from "./CaseClassifierTable";
import CaseClassifierKrona from "./CaseClassifierKrona";

export interface Classifier {
  name: string;
  db?: string;
  krona_id?: string;
}

interface CaseClassifiersProps {
  caseId: string;
  classifiers: Classifier[];
  samples: Sample[];
  showKrona: boolean;
  onSelectSample: (sampleId: string) => void;
  /** Analysis being viewed; null means the case's latest. */
  version: number | null;
}

// Renders the classifier results table and (optionally) the Krona iframe for the
// case's samples. The active classifier is mirrored in the URL so deep links and
// browser back/forward preserve the user's selected tab.
export default function CaseClassifiers({
  caseId,
  classifiers,
  samples,
  showKrona,
  onSelectSample,
  version,
}: Readonly<CaseClassifiersProps>) {
  const [searchParams, setSearchParams] = useSearchParams();
  const isTrana = samples.some((s) => s.trana);

  const [tab, setTab] = useState<string | null>(
    searchParams.get("classifier") ?? classifiers[0]?.name ?? null
  );

  useEffect(() => {
    if (!classifiers.length) return;
    const requested = searchParams.get("classifier");
    const match = classifiers.find((c) => c.name === requested);
    if (match) setTab(requested);
    else setTab((prev) => prev ?? classifiers[0].name);
  }, [classifiers, searchParams]);

  if (!classifiers.length) {
    return (
      <section className="bg-white border border-gray-100 rounded-lg p-8 text-center text-sm text-gray-400">
        No classifier results available for this case.
      </section>
    );
  }

  const activeClassifier = classifiers.find((c) => c.name === tab) ?? classifiers[0];

  return (
    <section className="bg-white border border-gray-100 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900 m-0">
          {isTrana ? "Taxonomic profile" : "Classifier results"}
        </h3>
        <div className="ml-auto flex gap-1.5">
          {classifiers.map((clf) => (
            <button
              key={clf.name}
              onClick={() => {
                setTab(clf.name);
                setSearchParams({ classifier: clf.name });
              }}
              className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                tab === clf.name
                  ? "bg-gray-900 text-white font-medium"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              {clf.name}
            </button>
          ))}
        </div>
      </div>

      <div className="px-4 pt-3 pb-1">
        <p className="text-xs text-gray-300 font-mono">{activeClassifier.db}</p>
      </div>

      <CaseClassifierTable
        activeClassifier={activeClassifier}
        samples={samples}
        isTrana={isTrana}
        onSelectSample={onSelectSample}
      />

      {showKrona && (
        <div className="p-4 border-t border-gray-50">
          <CaseClassifierKrona
            caseId={caseId}
            classifiers={classifiers}
            samples={samples}
            activeClassifier={activeClassifier}
            isTrana={isTrana}
            version={version}
          />
        </div>
      )}
    </section>
  );
}
