import { useState } from "react";
import {
  useAddNtcContaminant,
  useNtcContaminants,
  useRemoveNtcContaminant,
  useUpdateNtcContaminant,
} from "../../hooks/queries/useNtc";
import type { NtcContaminantItem } from "../../api/types";
import AddTaxonModal from "../AddTaxonModal";
import RemoveTaxonModal from "./RemoveTaxonModal";

interface NtcContaminantsPanelProps {
  canEdit: boolean;
  canDelete: boolean;
}

export default function NtcContaminantsPanel({
  canEdit,
  canDelete,
}: Readonly<NtcContaminantsPanelProps>) {
  const contaminantsQ = useNtcContaminants();
  const addMutation = useAddNtcContaminant();
  const updateMutation = useUpdateNtcContaminant();
  const removeMutation = useRemoveNtcContaminant();

  const [addOpen, setAddOpen] = useState(false);
  const [removeTarget, setRemoveTarget] = useState<NtcContaminantItem | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editMinReads, setEditMinReads] = useState(3);

  const items = contaminantsQ.data ?? [];

  async function saveMinReads(taxonId: number) {
    try {
      await updateMutation.mutateAsync({ taxonId, fields: { minReads: editMinReads } });
      setEditingId(null);
    } catch {
      alert("Failed to update threshold.");
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

  if (contaminantsQ.isError) {
    return (
      <section className="bg-white border border-gray-100 rounded-xl px-4 py-6 text-xs text-red-500 text-center">
        Failed to load known contaminants.
      </section>
    );
  }

  function renderBody() {
    if (contaminantsQ.isLoading) {
      return <p className="px-4 py-8 text-center text-xs text-gray-400">Loading…</p>;
    }
    if (items.length === 0) {
      return (
        <p className="px-4 py-8 text-center text-xs text-gray-400">
          No known contaminants on the list.
        </p>
      );
    }
    return (
      <table className="w-full text-left border-collapse">
        <thead>
          <tr>
            {[
              "Taxon",
              "Kingdom",
              "Tax ID",
              "Alert threshold",
              "Notes",
              "Added by",
              "Date added",
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
                <span className="bg-orange-50 text-orange-700 px-2 py-0.5 rounded text-xs">
                  {item.superkingdom ?? "—"}
                </span>
              </td>
              <td className="px-4 py-3 text-xs font-mono text-gray-400">{item.taxon_id}</td>
              <td className="px-4 py-3 text-xs text-gray-600">
                {editingId === item.taxon_id ? (
                  <div className="flex items-center gap-2">
                    <input
                      autoFocus
                      type="number"
                      min={1}
                      value={editMinReads}
                      onChange={(e) => setEditMinReads(Number.parseInt(e.target.value) || 1)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") saveMinReads(item.taxon_id);
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      className="w-20 text-xs border border-blue-300 rounded px-2 py-1 outline-none"
                    />
                    <button
                      onClick={() => saveMinReads(item.taxon_id)}
                      disabled={updateMutation.isPending}
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
                    <span className="font-mono">&gt; {item.min_reads} reads</span>
                    {canEdit && (
                      <button
                        onClick={() => {
                          setEditingId(item.taxon_id);
                          setEditMinReads(item.min_reads);
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
              <td className="px-4 py-3 text-xs text-gray-500 min-w-40">
                {item.notes ?? <span className="text-gray-300">—</span>}
              </td>
              <td className="px-4 py-3 text-xs text-gray-500">{item.added_by}</td>
              <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                {item.added_at?.slice(0, 10) ?? "—"}
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
    );
  }

  return (
    <>
      <section className="bg-white border border-gray-100 rounded-xl">
        <div className="flex items-center px-4 py-3 border-b border-gray-50">
          <div className="flex-1">
            <h2 className="text-xs font-medium text-gray-700">Known contaminants</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Triggers an alert on the NTC trends page and case list when detected in any NTC above
              the threshold.
            </p>
          </div>
          {canEdit && (
            <button onClick={() => setAddOpen(true)} className="btn-primary">
              + Add taxon
            </button>
          )}
        </div>
        {renderBody()}
      </section>

      {addOpen && (
        <AddTaxonModal
          title="Add known contaminant"
          showMinReads={true}
          onAdd={async (id, name, sk, notes, minReads) => {
            await addMutation.mutateAsync({
              taxonId: id,
              taxonName: name,
              superkingdom: sk ?? "",
              minReads,
              notes,
            });
          }}
          onClose={() => setAddOpen(false)}
        />
      )}

      {removeTarget && (
        <RemoveTaxonModal
          taxonName={removeTarget.taxon_name}
          listLabel="known contaminants list"
          busy={removeMutation.isPending}
          onConfirm={handleRemove}
          onCancel={() => setRemoveTarget(null)}
        />
      )}
    </>
  );
}
