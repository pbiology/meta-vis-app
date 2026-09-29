import { useState } from "react";
import { isAxiosError } from "axios";
import type { BulkAddReport, RejectedTaxon } from "../../api/types";
import { useBulkAddTaxonListEntries } from "../../hooks/queries/useTaxonLists";
import { axiosErrorDetail } from "../../utils/axiosError";
import { parseTaxonIds } from "../../utils/taxonIds";

/** Matches MAX_BULK_TAXA in backend/app/models/taxon_list.py. */
export const MAX_BULK_IDS = 75_000;

const REASON_LABEL: Record<RejectedTaxon["reason"], string> = {
  not_in_taxonomy: "Not in the taxonomy",
  merged: "Merged in NCBI into a taxon not in the taxonomy",
  deleted: "Deleted from NCBI",
  excluded_by_list: "On a conflicting list",
};

interface BulkAddTaxaModalProps {
  listId: string;
  listLabel: string;
  onClose: () => void;
}

interface Checked {
  /** The ids that were checked — what "Add" acts on, whatever the text box says now. */
  ids: number[];
  invalid: string[];
  report: BulkAddReport;
}

/** Ids the report puts in the "to add" group: checked minus skipped minus rejected. */
function idsToAdd({ ids, report }: Checked): number[] {
  const excluded = new Set([...report.already_on_list, ...report.rejected.map((r) => r.taxon_id)]);
  return ids.filter((id) => !excluded.has(id));
}

/**
 * Paste taxon ids, preview where each one goes, then add the accepted ones.
 * Every pasted value is accounted for in the preview; nothing is dropped
 * without the user seeing it.
 */
export default function BulkAddTaxaModal({
  listId,
  listLabel,
  onClose,
}: Readonly<BulkAddTaxaModalProps>) {
  const bulkMutation = useBulkAddTaxonListEntries(listId);
  const [text, setText] = useState("");
  const [reason, setReason] = useState("");
  const [checked, setChecked] = useState<Checked | null>(null);
  const [error, setError] = useState<string | null>(null);

  const parsed = parseTaxonIds(text);
  const tooMany = parsed.ids.length > MAX_BULK_IDS;

  async function check() {
    setError(null);
    try {
      const report = await bulkMutation.mutateAsync({ taxonIds: parsed.ids, dryRun: true });
      setChecked({ ids: parsed.ids, invalid: parsed.invalid, report });
    } catch (e) {
      setError(axiosErrorDetail(e, "Failed to check taxa."));
    }
  }

  async function add() {
    if (!checked) return;
    setError(null);
    try {
      const result = await bulkMutation.mutateAsync({
        taxonIds: idsToAdd(checked),
        reason: reason.trim() || null,
        dryRun: false,
      });
      if (result.added > 0) onClose();
      else setChecked({ ...checked, report: result });
    } catch (e) {
      // The list or taxonomy changed since the preview: show the fresh report.
      const fresh = isAxiosError(e) ? e.response?.data?.detail?.report : undefined;
      if (fresh) {
        setChecked({ ...checked, ids: idsToAdd(checked), report: fresh as BulkAddReport });
        setError("The list changed since the preview and nothing was added. Review and try again.");
      } else {
        setError(axiosErrorDetail(e, "Failed to add taxa."));
      }
    }
  }

  const toAddCount = checked?.report.to_add_count ?? 0;
  return (
    <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
      {/* `static` keeps the dialog in the centred flex wrapper: an open
          <dialog> is otherwise absolutely positioned by the browser. */}
      <dialog
        open
        aria-label={`Add taxa to ${listLabel}`}
        className="static m-0 bg-white rounded-xl border border-gray-100 shadow-lg p-6 w-[36rem] max-h-[85vh] flex flex-col gap-4"
      >
        <p className="text-sm font-medium text-gray-900">Add taxa to {listLabel}</p>

        {checked === null ? (
          <>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-500">
                NCBI taxon ids, separated by commas, spaces or new lines
              </span>
              <textarea
                autoFocus
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={8}
                placeholder="562, 1392, 11676"
                className="text-xs font-mono border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-blue-300"
              />
            </label>
            <p className={`text-xs ${tooMany ? "text-red-600" : "text-gray-400"}`}>
              {parsed.ids.length.toLocaleString()} ids
              {parsed.invalid.length > 0 && `, ${parsed.invalid.length} not recognised`}
              {tooMany && ` — at most ${MAX_BULK_IDS.toLocaleString()} per paste`}
            </p>
          </>
        ) : (
          <BulkAddPreview report={checked.report} invalid={checked.invalid} />
        )}

        {checked !== null && toAddCount > 0 && (
          <label className="flex flex-col gap-1">
            <span className="text-xs text-gray-500">Reason (applies to every taxon added)</span>
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={2000}
              className="text-xs border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-blue-300"
            />
          </label>
        )}

        {error && (
          <p role="alert" className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="btn-secondary">
            Cancel
          </button>
          {checked === null ? (
            <button
              onClick={check}
              disabled={parsed.ids.length === 0 || tooMany || bulkMutation.isPending}
              className="btn-primary disabled:opacity-50"
            >
              {bulkMutation.isPending ? "Checking…" : "Check"}
            </button>
          ) : (
            <>
              <button onClick={() => setChecked(null)} className="btn-secondary">
                Back
              </button>
              <button
                onClick={add}
                disabled={toAddCount === 0 || bulkMutation.isPending}
                className="btn-primary disabled:opacity-50"
              >
                {bulkMutation.isPending ? "Adding…" : `Add ${toAddCount.toLocaleString()} taxa`}
              </button>
            </>
          )}
        </div>
      </dialog>
    </div>
  );
}

function BulkAddPreview({
  report,
  invalid,
}: Readonly<{ report: BulkAddReport; invalid: string[] }>) {
  const rejectedCount = report.rejected.length + invalid.length;
  const byReason = new Map<RejectedTaxon["reason"], RejectedTaxon[]>();
  for (const r of report.rejected) byReason.set(r.reason, [...(byReason.get(r.reason) ?? []), r]);

  function copyRejected() {
    const values = [...invalid, ...report.rejected.map((r) => String(r.taxon_id))];
    navigator.clipboard?.writeText(values.join("\n")).catch(() => {
      alert("Could not copy to the clipboard.");
    });
  }

  return (
    <div className="flex flex-col gap-3 overflow-y-auto min-h-0 text-xs">
      <p className="text-gray-700">
        <span className="font-medium text-green-700">
          {report.to_add_count.toLocaleString()} to add
        </span>
        {" · "}
        {report.already_on_list.length.toLocaleString()} already on the list
        {" · "}
        <span className={rejectedCount > 0 ? "text-red-600" : ""}>
          {rejectedCount.toLocaleString()} rejected
        </span>
      </p>

      {rejectedCount > 0 && (
        <section>
          <div className="flex items-center mb-1">
            <p className="font-medium text-red-600 flex-1">Rejected — will not be added</p>
            <button onClick={copyRejected} className="text-blue-600 hover:text-blue-800">
              Copy rejected ids
            </button>
          </div>
          <ul className="flex flex-col gap-1 max-h-40 overflow-y-auto">
            {invalid.length > 0 && (
              <li>
                Not a taxon id ({invalid.length}):{" "}
                <span className="font-mono break-words">{invalid.join(", ")}</span>
              </li>
            )}
            {[...byReason].map(([reason, rows]) => (
              <li key={reason}>
                {REASON_LABEL[reason]} ({rows.length}):{" "}
                <span className="font-mono break-words">
                  {rows
                    .map((r) =>
                      r.merged_into === null ? r.taxon_id : `${r.taxon_id} → ${r.merged_into}`
                    )
                    .join(", ")}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {report.replaced.length > 0 && (
        <section>
          <p className="font-medium text-blue-700 mb-1">
            Replaced by the current NCBI id ({report.replaced.length})
          </p>
          <p className="font-mono text-gray-500 break-words max-h-24 overflow-y-auto">
            {report.replaced.map((r) => `${r.taxon_id} → ${r.merged_into}`).join(", ")}
          </p>
        </section>
      )}

      {report.already_on_list.length > 0 && (
        <section>
          <p className="font-medium text-gray-500 mb-1">Already on the list — skipped</p>
          <p className="font-mono text-gray-400 break-words max-h-24 overflow-y-auto">
            {report.already_on_list.join(", ")}
          </p>
        </section>
      )}

      {report.to_add_count > 0 && (
        <section>
          <p className="font-medium text-green-700 mb-1">
            To add
            {report.to_add_count > report.to_add_sample.length &&
              ` (first ${report.to_add_sample.length} shown)`}
          </p>
          <ul className="flex flex-col gap-0.5 max-h-40 overflow-y-auto">
            {report.to_add_sample.map((t) => (
              <li key={t.taxon_id}>
                <span className="font-mono text-gray-400">{t.taxon_id}</span>{" "}
                <span className="italic">{t.taxon_name}</span>
                {t.superkingdom && <span className="text-gray-400"> · {t.superkingdom}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
