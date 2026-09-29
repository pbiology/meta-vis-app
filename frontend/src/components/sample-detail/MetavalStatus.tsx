import type { MetavalSummary } from "../../api/types";

interface MetavalStatusProps {
  hasMetavalAnalysis: boolean;
  classifier: string;
  // This classifier's results, and the subset with no row in its table.
  results: MetavalSummary[];
  unmatched: MetavalSummary[];
  onSelectMetaval: (metavalId: string) => void;
}

function statusText(hasMetavalAnalysis: boolean, classifier: string, count: number): string {
  if (!hasMetavalAnalysis) return "Metaval: not run for this analysis.";
  if (count === 0) return `Metaval: no taxa examined for ${classifier}.`;
  return `Metaval: ${count} ${count === 1 ? "taxon" : "taxa"} examined for ${classifier}.`;
}

/**
 * One-line metaval summary above the taxonomy table. Tells "not run" apart
 * from "run, nothing examined" — no metaval pills means either — and lists
 * results that have no row in the table, which would otherwise not be shown.
 */
export default function MetavalStatus({
  hasMetavalAnalysis,
  classifier,
  results,
  unmatched,
  onSelectMetaval,
}: Readonly<MetavalStatusProps>) {
  return (
    <div className="flex flex-col gap-2 mb-3">
      <p className="text-xs text-gray-500">
        {statusText(hasMetavalAnalysis, classifier, results.length)}
      </p>
      {unmatched.length > 0 && (
        <p role="alert" className="text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2">
          {unmatched.length} metaval {unmatched.length === 1 ? "result has" : "results have"} no row
          in the {classifier} table:{" "}
          {unmatched.map((r, i) => (
            <span key={r._id}>
              {i > 0 && ", "}
              <button
                type="button"
                onClick={() => onSelectMetaval(r._id)}
                className="italic underline hover:text-amber-900"
              >
                {r.display_name}
              </button>
            </span>
          ))}
        </p>
      )}
    </div>
  );
}
