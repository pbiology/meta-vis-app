import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  useCreateTaxonList,
  useDeleteTaxonList,
  useTaxonLists,
  useUpdateTaxonList,
} from "../hooks/queries/useTaxonLists";
import TaxonListEntriesPanel from "../components/taxonomy/TaxonListEntriesPanel";
import type { TaxonListSummary } from "../api/types";
import { axiosErrorDetail } from "../utils/axiosError";

/**
 * Shared lists of taxa that users can choose to hide from the taxonomy table.
 * Writers create lists and add taxa; only admins remove taxa or delete lists.
 */
export default function DisplayFilters() {
  const { role, preferences, setPreferences } = useAuth();
  const canEdit = role !== "reader";
  const canDelete = role === "admin";

  const listsQ = useTaxonLists("display_filter");
  const createMutation = useCreateTaxonList();
  const updateMutation = useUpdateTaxonList();
  const deleteMutation = useDeleteTaxonList();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  // A new list is empty; open it straight into pasting ids.
  const [justCreatedId, setJustCreatedId] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [renaming, setRenaming] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TaxonListSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const lists = listsQ.data ?? [];
  const selected = lists.find((l) => l.list_id === selectedId) ?? lists[0] ?? null;

  async function handleCreate() {
    const name = newName.trim();
    if (!name) return;
    setError(null);
    try {
      const created = await createMutation.mutateAsync({ kind: "display_filter", name });
      setNewName("");
      setSelectedId(created.list_id);
      setJustCreatedId(created.list_id);
    } catch (e) {
      setError(axiosErrorDetail(e, "Failed to create list."));
    }
  }

  async function handleRename(listId: string) {
    const name = renaming?.trim();
    if (!name) return;
    setError(null);
    try {
      await updateMutation.mutateAsync({ listId, changes: { name } });
      setRenaming(null);
    } catch (e) {
      setError(axiosErrorDetail(e, "Failed to rename list."));
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    const listId = deleteTarget.list_id;
    setError(null);
    try {
      await deleteMutation.mutateAsync(listId);
      setDeleteTarget(null);
      setSelectedId(null);
      // The backend removed it from every user's preferences; bring this
      // session's copy in line so the table stops asking for its entries.
      if (preferences.active_display_filters.includes(listId)) {
        await setPreferences({
          active_display_filters: preferences.active_display_filters.filter((id) => id !== listId),
        });
      }
    } catch (e) {
      setError(axiosErrorDetail(e, "Failed to delete list."));
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <h1 className="text-sm font-medium text-gray-900 flex-1">Display filters</h1>
        {canEdit && (
          <div className="flex items-center gap-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              placeholder="New list name…"
              aria-label="New list name"
              maxLength={100}
              className="text-xs border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-blue-300"
            />
            <button
              onClick={handleCreate}
              disabled={!newName.trim() || createMutation.isPending}
              className="btn-primary disabled:opacity-50"
            >
              + New list
            </button>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-4">
        <p className="text-xs text-gray-500 max-w-2xl">
          Taxa on these lists can be hidden from the taxonomy table — each user picks which lists
          are active under <span className="font-medium">Hide lists</span>. Hiding is display only:
          read totals, reports and alerts are unaffected, and known pathogens are never hidden.
        </p>
        {error && (
          <p role="alert" className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">
            {error}
          </p>
        )}
        {listsQ.isLoading && <p className="text-sm text-gray-400">Loading…</p>}
        {listsQ.isError && <p className="text-sm text-red-500">Failed to load display filters.</p>}
        {!listsQ.isLoading && !listsQ.isError && lists.length === 0 && (
          <p className="text-sm text-gray-400">No display filters yet.</p>
        )}

        {selected && (
          <div className="flex gap-4 items-start">
            <nav
              className="w-56 flex-shrink-0 flex flex-col gap-1"
              aria-label="Display filter lists"
            >
              {lists.map((list) => (
                <button
                  key={list.list_id}
                  onClick={() => setSelectedId(list.list_id)}
                  className={`text-left px-3 py-2 rounded-lg text-xs flex items-center gap-2 ${
                    list.list_id === selected.list_id
                      ? "bg-gray-900 text-white"
                      : "text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  <span className="flex-1 truncate">{list.name}</span>
                  <span className="opacity-60">{list.entry_count}</span>
                </button>
              ))}
            </nav>

            <div className="flex-1 flex flex-col gap-3 min-w-0">
              <div className="flex items-center gap-2">
                {renaming !== null ? (
                  <>
                    <input
                      autoFocus
                      value={renaming}
                      onChange={(e) => setRenaming(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleRename(selected.list_id);
                        if (e.key === "Escape") setRenaming(null);
                      }}
                      aria-label="List name"
                      maxLength={100}
                      className="text-sm border border-blue-300 rounded px-2 py-1 outline-none"
                    />
                    <button
                      onClick={() => handleRename(selected.list_id)}
                      className="text-xs text-blue-500 hover:text-blue-700"
                    >
                      Save
                    </button>
                  </>
                ) : (
                  <h2 className="text-sm font-medium text-gray-900">{selected.name}</h2>
                )}
                <span className="text-xs text-gray-400 flex-1">
                  created by {selected.created_by}
                </span>
                {canEdit && renaming === null && (
                  <button
                    onClick={() => setRenaming(selected.name)}
                    className="text-xs text-gray-400 hover:text-gray-600"
                  >
                    Rename
                  </button>
                )}
                {canDelete && (
                  <button
                    onClick={() => setDeleteTarget(selected)}
                    className="text-xs text-gray-400 hover:text-red-500"
                  >
                    Delete list
                  </button>
                )}
              </div>
              <TaxonListEntriesPanel
                key={selected.list_id}
                listId={selected.list_id}
                listLabel={`"${selected.name}" display filter`}
                canEdit={canEdit}
                canDelete={canDelete}
                startWithBulkAdd={selected.list_id === justCreatedId}
              />
            </div>
          </div>
        )}
      </div>

      {deleteTarget && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl border border-gray-100 shadow-lg p-6 w-80 flex flex-col gap-4">
            <p className="text-sm font-medium text-gray-900">Delete list?</p>
            <p className="text-xs text-gray-500">
              This permanently deletes <span className="font-medium">{deleteTarget.name}</span> and
              its {deleteTarget.entry_count} taxa, and turns it off for every user who has it
              active.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteTarget(null)} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
                className="px-3 py-1.5 text-xs font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deleteMutation.isPending ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
