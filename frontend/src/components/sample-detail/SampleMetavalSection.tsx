import { useEffect, useState } from "react";
import type { MetavalResult, SampleProfile } from "../../api/types";

interface SampleMetavalSectionProps {
  classifiers: SampleProfile[];
  metavalResults: MetavalResult[];
  activeTab: string | null;
  onTabChange: (classifier: string) => void;
  onSelectMetaval: (metavalId: string) => void;
}

export default function SampleMetavalSection({
  classifiers,
  metavalResults,
  activeTab,
  onTabChange,
  onSelectMetaval,
}: Readonly<SampleMetavalSectionProps>) {
  // Reset paged display when the tab changes; keeps "Load more" predictable.
  const [displayCount, setDisplayCount] = useState(10);
  useEffect(() => {
    setDisplayCount(10);
  }, [activeTab]);

  const filtered = metavalResults.filter(
    (r) => (r as { classifier?: string }).classifier === activeTab
  );
  const displayed = filtered.slice(0, displayCount);
  const hasMore = filtered.length > displayCount;

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">Metaval</p>
        {metavalResults.length > 0 && (
          <div className="flex gap-1.5">
            {classifiers.map((clf) => {
              const hasResults = metavalResults.some(
                (r) => (r as { classifier?: string }).classifier === clf.classifier
              );
              if (!hasResults) return null;
              return (
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
              );
            })}
          </div>
        )}
      </div>
      {metavalResults.length === 0 ? (
        <p className="px-4 py-6 text-xs text-gray-300 text-center">No viral taxon found</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr>
                  <th className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100">
                    Viral taxon
                  </th>
                </tr>
              </thead>
              <tbody>
                {displayed.map((r) => {
                  const taxonName = (r as { taxon_name?: string }).taxon_name ?? "";
                  return (
                    <tr key={r._id} className="border-t border-gray-50 hover:bg-gray-50">
                      <td className="px-4 py-2.5">
                        <button
                          onClick={() => onSelectMetaval(r._id)}
                          className="text-xs italic text-gray-700 hover:text-blue-600 underline transition-colors text-left"
                        >
                          {taxonName.replace(/^taxid_\d+_/, "").replace(/-/g, " ")}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <div className="px-4 py-3 border-t border-gray-50">
              <button
                onClick={() => setDisplayCount((n) => n + 10)}
                className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
              >
                Load more ({filtered.length - displayCount} remaining)
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
