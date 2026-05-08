import { useState } from "react";
import {
  useAddToNtcIgnorelist,
  useNtcIgnorelist,
  useRemoveFromNtcIgnorelist,
  useUpdateNtcIgnorelistNote,
} from "../../hooks/queries/useNtc";
import type { IgnorelistItem } from "../../api/types";
import AddTaxonModal from "../AddTaxonModal";
import RemoveTaxonModal from "./RemoveTaxonModal";

interface NtcIgnoreListPanelProps {
  canEdit: boolean;
  canDelete: boolean;
}

export default function NtcIgnoreListPanel({
  canEdit,
  canDelete,
}: Readonly<NtcIgnoreListPanelProps>) {
  const ignorelistQ = useNtcIgnorelist();
  const addMutation = useAddToNtcIgnorelist();
  const updateNoteMutation = useUpdateNtcIgnorelistNote();
  const removeMutation = useRemoveFromNtcIgnorelist();

  const [addOpen, setAddOpen] = useState(false);
  const [removeTarget, setRemoveTarget] = useState<IgnorelistItem | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const items = ignorelistQ.data ?? [];

  async function saveEdit(taxonId: number) {
    try {
      await updateNoteMutation.mutateAsync({ taxonId, reason: editText.trim() || null });
      setEditingId(null);
    } catch {
      alert("Failed to save note.");
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

  if (ignorelistQ.isError) {
    return (
      <section className="bg-white border border-gray-100 rounded-xl px-4 py-6 text-xs text-red-500 text-center">
        Failed to load NTC ignorelist.
      </section>
    );
  }

  return (
    <>
      <section className="bg-white border border-gray-100 rounded-xl">
        <div className="flex items-center px-4 py-3 border-b border-gray-50">
          <div className="flex-1">
            <h2 className="text-xs font-medium text-gray-700">Ignored taxa</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Excluded from all NTC charts and calculations.
            </p>
          </div>
          {canEdit && (
            <button onClick={() => setAddOpen(true)} className="btn-primary">
              + Add taxon
            </button>
          )}
        </div>
        {ignorelistQ.isLoading ? (
          <p className="px-4 py-8 text-center text-xs text-gray-400">Loading…</p>
        ) : items.length === 0 ? (
          <p className="px-4 py-8 text-center text-xs text-gray-400">No taxa on the ignorelist.</p>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr>
                {[
                  "Taxon",
                  "Kingdom",
                  "Tax ID",
                  "Added by",
                  "Date added",
                  "Reason",
                  ...(canEdit ? [""] : []),
                ].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-50 whitespace-nowrap"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.taxon_id} className="border-b border-gray-50">
                  <td className="px-4 py-3 text-xs text-gray-700 italic">
                    {item.taxon_name.replace(/-/g, " ")}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-xs">
                      {item.superkingdom ?? "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs font-mono text-gray-400">{item.taxon_id}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">{item.added_by}</td>
                  <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                    {item.added_at?.slice(0, 10) ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 min-w-48">
                    {editingId === item.taxon_id ? (
                      <div className="flex items-center gap-2">
                        <input
                          autoFocus
                          type="text"
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") saveEdit(item.taxon_id);
                            if (e.key === "Escape") setEditingId(null);
                          }}
                          className="flex-1 text-xs border border-blue-300 rounded px-2 py-1 outline-none"
                          placeholder="Add a reason…"
                        />
                        <button
                          onClick={() => saveEdit(item.taxon_id)}
                          disabled={updateNoteMutation.isPending}
                          className="text-xs text-blue-500 hover:text-blue-700 disabled:opacity-50"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="text-xs text-gray-400 hover:text-gray-600"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 group">
                        <span className={item.reason ? "" : "text-gray-300"}>
                          {item.reason ?? "No reason"}
                        </span>
                        {canEdit && (
                          <button
                            onClick={() => {
                              setEditingId(item.taxon_id);
                              setEditText(item.reason ?? "");
                            }}
                            className="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-gray-500 transition-all"
                          >
                            <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
                              <path
                                d="M11 2l3 3-8 8H3v-3l8-8z"
                                stroke="currentColor"
                                strokeWidth="1.3"
                                strokeLinejoin="round"
                              />
                            </svg>
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                  {canEdit && (
                    <td className="px-4 py-3 text-right">
                      {canDelete && (
                        <button
                          onClick={() => setRemoveTarget(item)}
                          className="text-xs text-gray-300 hover:text-red-500 transition-colors"
                        >
                          Remove
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {addOpen && (
        <AddTaxonModal
          title="Add to NTC ignorelist"
          showMinReads={false}
          onAdd={async (id, name, sk, notes) => {
            await addMutation.mutateAsync({
              taxonId: id,
              taxonName: name,
              superkingdom: sk ?? "",
              reason: notes,
            });
          }}
          onClose={() => setAddOpen(false)}
        />
      )}

      {removeTarget && (
        <RemoveTaxonModal
          taxonName={removeTarget.taxon_name}
          listLabel="NTC ignorelist"
          busy={removeMutation.isPending}
          onConfirm={handleRemove}
          onCancel={() => setRemoveTarget(null)}
        />
      )}
    </>
  );
}
