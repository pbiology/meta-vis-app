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
import {
  EditPencilButton,
  NtcPanelCard,
  NtcPanelStatus,
  NtcTableHeaderRow,
  NtcTaxonCells,
} from "./NtcListChrome";

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

  const headers = [
    "Taxon",
    "Kingdom",
    "Tax ID",
    "Alert threshold",
    "Notes",
    "Added by",
    "Date added",
    ...(canEdit ? [""] : []),
  ];

  function renderBody() {
    if (contaminantsQ.isLoading) return <NtcPanelStatus message="Loading…" />;
    if (items.length === 0) return <NtcPanelStatus message="No known contaminants on the list." />;
    return (
      <table className="w-full text-left border-collapse">
        <thead>
          <NtcTableHeaderRow headers={headers} />
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.taxon_id} className="border-b border-gray-50">
              <NtcTaxonCells
                taxonName={item.taxon_name}
                superkingdom={item.superkingdom}
                taxonId={item.taxon_id}
                kingdomTone="orange"
              />
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
                      <EditPencilButton
                        onClick={() => {
                          setEditingId(item.taxon_id);
                          setEditMinReads(item.min_reads);
                        }}
                      />
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
      <NtcPanelCard
        title="Known contaminants"
        description="Triggers an alert on the NTC trends page and case list when detected in any NTC above the threshold."
        action={
          canEdit && (
            <button onClick={() => setAddOpen(true)} className="btn-primary">
              + Add taxon
            </button>
          )
        }
      >
        {renderBody()}
      </NtcPanelCard>

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
