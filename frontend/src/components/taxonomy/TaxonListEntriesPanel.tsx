import { useState } from "react";
import type { TaxonListEntry } from "../../api/types";
import {
  useAddTaxonListEntry,
  useRemoveTaxonListEntry,
  useTaxonListPage,
  useUpdateTaxonListEntry,
} from "../../hooks/queries/useTaxonLists";
import AddTaxonModal from "../AddTaxonModal";
import BulkAddTaxaModal from "./BulkAddTaxaModal";
import RemoveTaxonModal from "../ntc/RemoveTaxonModal";

interface TaxonListEntriesPanelProps {
  listId: string;
  listLabel: string;
  canEdit: boolean;
  canDelete: boolean;
  /** Open the paste-many dialog straight away, e.g. for a list just created. */
  startWithBulkAdd?: boolean;
}

const PAGE_SIZE = 100;

/**
 * View and edit the taxa on one list, a page at a time with server-side
 * search, so a list of tens of thousands stays usable. Generic over list kind.
 */
export default function TaxonListEntriesPanel({
  listId,
  listLabel,
  canEdit,
  canDelete,
  startWithBulkAdd = false,
}: Readonly<TaxonListEntriesPanelProps>) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const entriesQ = useTaxonListPage(listId, {
    offset: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    q: search.trim() || null,
  });
  const total = entriesQ.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const addMutation = useAddTaxonListEntry(listId);
  const updateMutation = useUpdateTaxonListEntry(listId);
  const removeMutation = useRemoveTaxonListEntry(listId);

  const [addOpen, setAddOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(startWithBulkAdd && canEdit);
  const [removeTarget, setRemoveTarget] = useState<TaxonListEntry | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  async function saveReason(taxonId: number) {
    try {
      await updateMutation.mutateAsync({
        taxonId,
        changes: { reason: editText.trim() || null },
      });
      setEditingId(null);
    } catch {
      alert("Failed to save reason.");
    }
  }

  async function handleRemove() {
    if (!removeTarget) return;
    try {
      await removeMutation.mutateAsync(removeTarget.taxon_id);
      setRemoveTarget(null);
    } catch {
      alert("Failed to remove taxon.");
    }
  }

  function renderBody() {
    if (entriesQ.isLoading)
      return <p className="px-4 py-10 text-center text-sm text-gray-400">Loading…</p>;
    if (entriesQ.isError)
      return (
        <p className="px-4 py-10 text-center text-sm text-red-500">Failed to load {listLabel}.</p>
      );
    const items = entriesQ.data?.items ?? [];
    if (items.length === 0)
      return (
        <p className="px-4 py-10 text-center text-sm text-gray-400">
          {search.trim() ? "No taxa match your search." : "No taxa on this list yet."}
        </p>
      );
    return (
      <table className="w-full text-left border-collapse">
        <thead>
          <tr>
            {[
              "Taxon",
              "Kingdom",
              "Tax ID",
              "Reason",
              "Added by",
              "Date added",
              ...(canDelete ? [""] : []),
            ].map((h) => (
              <th
                key={h}
                className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100 whitespace-nowrap"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.taxon_id} className="border-b border-gray-50">
              <td className="px-4 py-3 text-xs text-gray-700 italic">{item.taxon_name}</td>
              <td className="px-4 py-3 text-xs text-gray-500">{item.superkingdom ?? "—"}</td>
              <td className="px-4 py-3 text-xs font-mono text-gray-400">
                {item.taxon_id}
                {(item.merged_ids?.length ?? 0) > 0 && (
                  <span
                    className="block font-sans text-gray-300"
                    title="Retired NCBI ids merged into this taxon; the list matches them too"
                  >
                    also matches {item.merged_ids!.join(", ")}
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-xs text-gray-500 min-w-48">
                {editingId === item.taxon_id ? (
                  <div className="flex items-center gap-2">
                    <input
                      autoFocus
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") saveReason(item.taxon_id);
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      className="flex-1 text-xs border border-blue-300 rounded px-2 py-1 outline-none"
                    />
                    <button
                      onClick={() => saveReason(item.taxon_id)}
                      disabled={updateMutation.isPending}
                      className="text-xs text-blue-500 hover:text-blue-700 disabled:opacity-50"
                    >
                      Save
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    disabled={!canEdit}
                    onClick={() => {
                      setEditingId(item.taxon_id);
                      setEditText(item.reason ?? "");
                    }}
                    className="text-left disabled:cursor-default enabled:hover:text-gray-700"
                  >
                    {item.reason ?? <span className="text-gray-300">—</span>}
                  </button>
                )}
              </td>
              <td className="px-4 py-3 text-xs text-gray-500">{item.added_by}</td>
              <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                {item.added_at?.slice(0, 10) ?? "—"}
              </td>
              {canDelete && (
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => setRemoveTarget(item)}
                    className="text-xs text-gray-300 hover:text-red-500 transition-colors"
                  >
                    Remove
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-50">
        <input
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          placeholder="Search by name or taxon id…"
          aria-label="Search taxa on this list"
          maxLength={100}
          className="flex-1 text-xs border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-blue-300"
        />
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {total.toLocaleString()} {total === 1 ? "taxon" : "taxa"}
        </span>
      </div>
      {canEdit && (
        <div className="flex justify-end gap-2 px-4 py-3 border-b border-gray-50">
          <button onClick={() => setBulkOpen(true)} className="btn-secondary">
            + Add many
          </button>
          <button onClick={() => setAddOpen(true)} className="btn-primary">
            + Add taxon
          </button>
        </div>
      )}
      {renderBody()}
      {pageCount > 1 && (
        <div className="flex items-center justify-end gap-3 px-4 py-3 text-xs text-gray-500">
          <button
            onClick={() => setPage((p) => p - 1)}
            disabled={page === 0}
            className="btn-secondary disabled:opacity-50"
          >
            Previous
          </button>
          <span>
            Page {page + 1} of {pageCount}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page + 1 >= pageCount}
            className="btn-secondary disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}

      {addOpen && (
        <AddTaxonModal
          title={`Add to ${listLabel}`}
          showMinReads={false}
          onAdd={async (taxonId, reason) => {
            await addMutation.mutateAsync({ taxonId, reason });
          }}
          onClose={() => setAddOpen(false)}
        />
      )}

      {bulkOpen && (
        <BulkAddTaxaModal
          listId={listId}
          listLabel={listLabel}
          onClose={() => setBulkOpen(false)}
        />
      )}

      {removeTarget && (
        <RemoveTaxonModal
          taxonName={removeTarget.taxon_name}
          listLabel={listLabel}
          busy={removeMutation.isPending}
          onConfirm={handleRemove}
          onCancel={() => setRemoveTarget(null)}
        />
      )}
    </section>
  );
}
