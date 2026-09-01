import { useState } from "react";
import type { CarryForwardResponse } from "../../../api/cases";
import type { AnalysisSummary } from "../../../api/types";
import { useCarryForwardReport, useCase } from "../../../hooks/queries/useCases";

interface ReportCarryForwardPromptProps {
  caseId: string;
  /** Version being viewed; null means the latest analysis. */
  version: number | null;
  analyses: AnalysisSummary[];
  canEdit: boolean;
}

/**
 * Offers to copy an earlier analysis's report draft into this one.
 *
 * Deliberately opt-in: a taxon picked against one run's data should not
 * silently enter another run's report. The server keeps only picks whose sample
 * and taxon still exist here, and reports everything it dropped.
 */
export default function ReportCarryForwardPrompt({
  caseId,
  version,
  analyses,
  canEdit,
}: Readonly<ReportCarryForwardPromptProps>) {
  const [result, setResult] = useState<CarryForwardResponse | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const carryForward = useCarryForwardReport();

  const currentVersion = version ?? analyses.find((a) => a.is_latest)?.version ?? null;
  const previous = analyses
    .filter((a) => currentVersion != null && a.version < currentVersion)
    .sort((a, b) => b.version - a.version)[0];

  // The list summaries omit report_selections to keep the payload slim, so the
  // previous analysis is fetched only when there is one to ask about.
  const previousQ = useCase(caseId, previous ? previous.version : null);
  const previousSelections = previous ? (previousQ.data?.analysis?.report_selections ?? {}) : {};
  const previousCount = Object.keys(previousSelections).length;

  if (!canEdit || !previous || currentVersion == null || dismissed) return null;

  if (result) {
    const appliedCount = Object.keys(result.applied).length;
    return (
      <section className="no-print bg-blue-50 border border-blue-100 rounded-lg px-5 py-3">
        <p className="text-xs text-blue-900 m-0">
          Copied selections for {appliedCount} {appliedCount === 1 ? "sample" : "samples"} from v
          {result.from_version}.
        </p>
        {result.dropped.length > 0 && (
          <ul className="text-xs text-blue-800 mt-2 mb-0 pl-4 list-disc">
            {result.dropped.map((d) => (
              <li key={`${d.sample_id}-${d.reason}`}>
                <span className="font-mono">{d.sample_id}</span>: {d.reason}
                {d.taxon_ids?.length ? ` (${d.taxon_ids.join(", ")})` : ""}
              </li>
            ))}
          </ul>
        )}
      </section>
    );
  }

  if (previousCount === 0) return null;

  return (
    <section className="no-print bg-amber-50 border border-amber-100 rounded-lg px-5 py-3 flex items-center justify-between gap-4">
      <p className="text-xs text-amber-900 m-0">
        Analysis v{previous.version} has a report draft covering {previousCount}{" "}
        {previousCount === 1 ? "sample" : "samples"}. Copy its selections into v{currentVersion}?
        Picks whose sample or taxon are absent here will be dropped.
      </p>
      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="text-xs px-3 py-1.5 rounded-md border border-amber-200 bg-white text-amber-800 hover:bg-amber-100 transition-colors"
        >
          Not now
        </button>
        <button
          type="button"
          disabled={carryForward.isPending}
          onClick={async () => {
            try {
              const res = await carryForward.mutateAsync({
                caseId,
                version: currentVersion,
                fromVersion: previous.version,
              });
              setResult(res);
            } catch {
              alert("Failed to copy report selections.");
            }
          }}
          className="text-xs px-3 py-1.5 rounded-md bg-amber-600 text-white hover:bg-amber-700 transition-colors disabled:opacity-50"
        >
          {carryForward.isPending ? "Copying…" : `Copy from v${previous.version}`}
        </button>
      </div>
    </section>
  );
}
