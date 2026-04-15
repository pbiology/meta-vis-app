import { useState, useEffect } from "react";
import { getPathogens, addToPathogens, removeFromPathogens } from "../api/alerts";
import { useAuth } from "../context/AuthContext";

function superkingdomFromLineage(lineage = "") {
  for (const sk of ["Viruses", "Bacteria", "Eukaryota", "Archaea"]) {
    if (lineage.includes(sk)) return sk;
  }
  return null;
}

// Cellular organisms (Bacteria, Archaea, Eukaryota) have a populated lineage
// string in NCBI esummary, which includes the kingdom name directly.
// Viruses have an empty lineage because they sit outside the cellular organism
// hierarchy — instead, NCBI always populates genbankdivision for them.
const GENBANK_DIVISION_TO_KINGDOM = {
  Viruses: "Viruses",
  Phages: "Viruses",
  Bacteria: "Bacteria",
  Archaea: "Archaea",
  Mammals: "Eukaryota",
  Primates: "Eukaryota",
  Rodents: "Eukaryota",
  Vertebrates: "Eukaryota",
  Invertebrates: "Eukaryota",
  Plants: "Eukaryota",
  Fungi: "Eukaryota",
};

async function lookupTaxon(taxonId) {
  const url = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=taxonomy&id=${taxonId}&retmode=json`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("NCBI request failed");
  const data = await res.json();
  const result = data?.result?.[String(taxonId)];
  if (!result || result.status === "error") throw new Error("Taxon not found");
  // For cellular organisms the lineage string contains the kingdom name.
  // For viruses the lineage is empty — use genbankdivision as fallback.
  const superkingdom =
    superkingdomFromLineage(result.lineage ?? "") ??
    GENBANK_DIVISION_TO_KINGDOM[result.genbankdivision] ??
    null;
  return {
    name: result.scientificname,
    superkingdom,
  };
}

const EMPTY_FORM = { taxon_id: "", taxon_name: "", superkingdom: null, notes: "" };

export default function KnownPathogens() {
  const { role } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [removeTarget, setRemoveTarget] = useState(null);
  const [removing, setRemoving] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [addForm, setAddForm] = useState(EMPTY_FORM);
  const [lookingUp, setLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState(null);
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState(null);

  useEffect(() => {
    getPathogens()
      .then(setItems)
      .catch(() => setError("Failed to load pathogens list."))
      .finally(() => setLoading(false));
  }, []);

  async function handleLookup() {
    const id = parseInt(addForm.taxon_id, 10);
    if (isNaN(id)) {
      setLookupError("Enter a valid taxon ID first.");
      return;
    }
    setLookingUp(true);
    setLookupError(null);
    setAddForm((f) => ({ ...f, taxon_name: "", superkingdom: null }));
    try {
      const { name, superkingdom } = await lookupTaxon(id);
      setAddForm((f) => ({
        ...f,
        taxon_name: name,
        superkingdom,
      }));
    } catch {
      setLookupError("Could not find taxon in NCBI. Check the ID and try again.");
    } finally {
      setLookingUp(false);
    }
  }

  async function handleAdd() {
    const id = parseInt(addForm.taxon_id, 10);
    if (isNaN(id) || !addForm.taxon_name.trim()) {
      setAddError("Look up a taxon ID before adding.");
      return;
    }
    setAdding(true);
    setAddError(null);
    try {
      const doc = await addToPathogens(
        id,
        addForm.taxon_name.trim(),
        addForm.superkingdom,
        addForm.notes.trim() || null
      );
      setItems((prev) => [doc, ...prev]);
      setAddOpen(false);
      setAddForm(EMPTY_FORM);
    } catch (e) {
      setAddError(e?.response?.data?.detail ?? "Failed to add taxon.");
    } finally {
      setAdding(false);
    }
  }

  function handleCloseAdd() {
    setAddOpen(false);
    setAddForm(EMPTY_FORM);
    setAddError(null);
    setLookupError(null);
  }

  async function handleRemove() {
    setRemoving(true);
    try {
      await removeFromPathogens(removeTarget.taxon_id);
      setItems((prev) => prev.filter((i) => i.taxon_id !== removeTarget.taxon_id));
      setRemoveTarget(null);
    } catch {
      alert("Failed to remove taxon.");
    } finally {
      setRemoving(false);
    }
  }

  const lookedUp = !!addForm.taxon_name;

  return (
    <div className="flex flex-col h-full">
      {/* Topbar */}
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <h1 className="text-sm font-medium text-gray-900 flex-1">Known pathogens</h1>
        {role !== "reader" && (
          <button onClick={() => setAddOpen(true)} className="btn-primary">
            + Add taxon
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        {loading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">
            Loading…
          </div>
        )}
        {error && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">{error}</div>
        )}
        {!loading && !error && (
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
                        {item.notes ?? <span className="text-gray-300">—</span>}
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

      {/* Add modal */}
      {addOpen && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl border border-gray-100 shadow-lg p-6 w-96 flex flex-col gap-4">
            <p className="text-sm font-medium text-gray-900">Add known pathogen</p>
            <div className="flex flex-col gap-3">
              {/* Taxon ID + lookup */}
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500">NCBI Taxon ID</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    value={addForm.taxon_id}
                    onChange={(e) => {
                      if (!/^\d*$/.test(e.target.value)) return;
                      setAddForm((f) => ({
                        ...EMPTY_FORM,
                        taxon_id: e.target.value,
                        notes: f.notes,
                      }));
                      setLookupError(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleLookup();
                    }}
                    placeholder="e.g. 11520"
                    className="flex-1 text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-blue-300"
                  />
                  <button
                    onClick={handleLookup}
                    disabled={lookingUp || !addForm.taxon_id}
                    className="text-xs px-3 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-40 whitespace-nowrap"
                  >
                    {lookingUp ? "Looking up…" : "Look up"}
                  </button>
                </div>
                {lookupError && <p className="text-xs text-red-500 mt-0.5">{lookupError}</p>}
              </div>

              {/* Auto-filled from NCBI — read-only, only shown after successful lookup */}
              {lookedUp && (
                <>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-gray-500">Taxon name</label>
                    <div className="text-xs border border-gray-100 bg-gray-50 rounded-lg px-3 py-2 text-gray-700 italic">
                      {addForm.taxon_name}
                    </div>
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-gray-500">Kingdom</label>
                    <div className="text-xs border border-gray-100 bg-gray-50 rounded-lg px-3 py-2 text-gray-700">
                      {addForm.superkingdom ?? "Unknown"}
                    </div>
                  </div>
                </>
              )}

              {/* Notes — always editable */}
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500">Notes (optional)</label>
                <input
                  type="text"
                  value={addForm.notes}
                  onChange={(e) => setAddForm((f) => ({ ...f, notes: e.target.value }))}
                  placeholder="e.g. Notifiable disease"
                  className="text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-blue-300"
                />
              </div>
            </div>

            {addError && <p className="text-xs text-red-500">{addError}</p>}

            <div className="flex gap-2 justify-end">
              <button onClick={handleCloseAdd} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={handleAdd}
                disabled={adding || !lookedUp}
                className="btn-primary disabled:opacity-50"
              >
                {adding ? "Adding…" : "Add pathogen"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Remove confirmation modal */}
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
                disabled={removing}
                className="px-3 py-1.5 text-xs font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {removing ? "Removing…" : "Remove"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
