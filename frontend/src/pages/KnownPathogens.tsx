import { useState } from "react";
import {
  useAddToPathogens,
  usePathogens,
  useRemoveFromPathogens,
} from "../hooks/queries/useAlerts";
import { useAuth } from "../context/AuthContext";
import type { PathogenItem } from "../api/types";
import AddTaxonModal from "../components/AddTaxonModal";

export default function KnownPathogens() {
  const { role } = useAuth();
  const { data: items = [], isLoading, isError } = usePathogens();
  const addMutation = useAddToPathogens();
  const removeMutation = useRemoveFromPathogens();
  const [removeTarget, setRemoveTarget] = useState<PathogenItem | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  async function handleAdd(
    id: number,
    name: string,
    superkingdom: string | null,
    notes: string | null
  ) {
    await addMutation.mutateAsync({
      taxonId: id,
      taxonName: name,
      superkingdom: superkingdom ?? "Viruses",
      notes,
    });
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

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <h1 className="text-sm font-medium text-gray-900 flex-1">Known pathogens</h1>
        {role !== "reader" && (
          <button onClick={() => setAddOpen(true)} className="btn-primary">
            + Add taxon
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        {isLoading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">
            Loading…
          </div>
        )}
        {isError && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">
            Failed to load pathogens list.
          </div>
        )}
        {!isLoading && !isError && (
          <section className="bg-white border border-gray-100 rounded-xl">
            {items.length === 0 ? (
              <p className="px-4 py-10 text-center text-sm text-gray-400">
                No known pathogens on the list yet.
              </p>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr>
                    {[
                      "Taxon",
                      "Kingdom",
                      "Tax ID",
                      "Notes",
                      "Added by",
                      "Date added",
                      ...(role !== "reader" ? [""] : []),
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
                      <td className="px-4 py-3 text-xs text-gray-700 italic">
                        {item.taxon_name.replace(/-/g, " ")}
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        <span className="bg-red-50 text-red-700 px-2 py-0.5 rounded text-xs font-medium">
                          {item.superkingdom}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs font-mono text-gray-400">{item.taxon_id}</td>
                      <td className="px-4 py-3 text-xs text-gray-500 min-w-48">
                        {item.reason ?? <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">{item.added_by}</td>
                      <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                        {item.added_at?.slice(0, 10) ?? "—"}
                      </td>
                      {role !== "reader" && (
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
            )}
          </section>
        )}
      </div>

      {addOpen && (
        <AddTaxonModal
          title="Add known pathogen"
          showMinReads={false}
          onAdd={async (id, name, superkingdom, notes) => {
            await handleAdd(id, name, superkingdom, notes);
          }}
          onClose={() => setAddOpen(false)}
        />
      )}

      {removeTarget && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl border border-gray-100 shadow-lg p-6 w-80 flex flex-col gap-4">
            <p className="text-sm font-medium text-gray-900">Remove pathogen?</p>
            <p className="text-xs text-gray-500">
              This will permanently remove{" "}
              <span className="italic font-medium">
                {removeTarget.taxon_name.replace(/-/g, " ")}
              </span>{" "}
              from the known pathogens list. Taxa in samples will no longer be flagged. This cannot
              be undone.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setRemoveTarget(null)} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={handleRemove}
                disabled={removeMutation.isPending}
                className="px-3 py-1.5 text-xs font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {removeMutation.isPending ? "Removing…" : "Remove"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
