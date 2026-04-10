import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  getNtcIgnorelist,
  addToNtcIgnorelist,
  updateNtcIgnorelistNote,
  removeFromNtcIgnorelist,
  getNtcContaminants,
  addNtcContaminant,
  updateNtcContaminant,
  removeNtcContaminant,
} from "../api/ntc";

// ---------------------------------------------------------------------------
// NCBI taxon lookup (shared with KnownPathogens)
// ---------------------------------------------------------------------------

function superkingdomFromLineage(lineage = "") {
  for (const sk of ["Viruses", "Bacteria", "Eukaryota", "Archaea"]) {
    if (lineage.includes(sk)) return sk;
  }
  return null;
}

async function lookupTaxon(taxonId) {
  const url = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=taxonomy&id=${taxonId}&retmode=json`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("NCBI request failed");
  const data = await res.json();
  const result = data?.result?.[String(taxonId)];
  if (!result || result.status === "error") throw new Error("Taxon not found");
  return {
    name: result.scientificname,
    superkingdom: superkingdomFromLineage(result.lineage ?? ""),
  };
}

const EMPTY_FORM = { taxon_id: "", taxon_name: "", superkingdom: null, notes: "", min_reads: 3 };

// ---------------------------------------------------------------------------
// Shared add-taxon modal
// ---------------------------------------------------------------------------

function AddTaxonModal({ title, showMinReads, onAdd, onClose }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [lookingUp, setLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState(null);
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState(null);

  async function handleLookup() {
    const id = parseInt(form.taxon_id, 10);
    if (isNaN(id)) {
      setLookupError("Enter a valid taxon ID first.");
      return;
    }
    setLookingUp(true);
    setLookupError(null);
    setForm((f) => ({ ...f, taxon_name: "", superkingdom: null }));
    try {
      const { name, superkingdom } = await lookupTaxon(id);
      setForm((f) => ({ ...f, taxon_name: name, superkingdom: superkingdom ?? "Bacteria" }));
    } catch {
      setLookupError("Could not find taxon in NCBI. Check the ID and try again.");
    } finally {
      setLookingUp(false);
    }
  }

  async function handleSubmit() {
    const id = parseInt(form.taxon_id, 10);
    if (isNaN(id) || !form.taxon_name.trim()) {
      setAddError("Look up a taxon ID before adding.");
      return;
    }
    setAdding(true);
    setAddError(null);
    try {
      await onAdd(
        id,
        form.taxon_name.trim(),
        form.superkingdom,
        form.notes.trim() || null,
        form.min_reads
      );
      onClose();
    } catch (e) {
      setAddError(e?.response?.data?.detail ?? "Failed to add taxon.");
    } finally {
      setAdding(false);
    }
  }

  const lookedUp = !!form.taxon_name;

  return (
    <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl border border-gray-100 shadow-lg p-6 w-96 flex flex-col gap-4">
        <p className="text-sm font-medium text-gray-900">{title}</p>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">NCBI Taxon ID</label>
            <div className="flex gap-2">
              <input
                type="text"
                inputMode="numeric"
                value={form.taxon_id}
                onChange={(e) => {
                  if (!/^\d*$/.test(e.target.value)) return;
                  setForm((f) => ({
                    ...EMPTY_FORM,
                    taxon_id: e.target.value,
                    notes: f.notes,
                    min_reads: f.min_reads,
                  }));
                  setLookupError(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleLookup();
                }}
                placeholder="e.g. 1743"
                className="flex-1 text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-blue-300"
              />
              <button
                onClick={handleLookup}
                disabled={lookingUp || !form.taxon_id}
                className="text-xs px-3 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-40 whitespace-nowrap"
              >
                {lookingUp ? "Looking up…" : "Look up"}
              </button>
            </div>
            {lookupError && <p className="text-xs text-red-500 mt-0.5">{lookupError}</p>}
          </div>
          {lookedUp && (
            <>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500">Taxon name</label>
                <div className="text-xs border border-gray-100 bg-gray-50 rounded-lg px-3 py-2 text-gray-700 italic">
                  {form.taxon_name}
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500">Kingdom</label>
                <div className="text-xs border border-gray-100 bg-gray-50 rounded-lg px-3 py-2 text-gray-700">
                  {form.superkingdom ?? "Unknown"}
                </div>
              </div>
            </>
          )}
          {showMinReads && (
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">Alert threshold (min reads)</label>
              <input
                type="number"
                min={1}
                value={form.min_reads}
                onChange={(e) =>
                  setForm((f) => ({ ...f, min_reads: parseInt(e.target.value) || 1 }))
                }
                className="text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-blue-300 w-24"
              />
              <p className="text-xs text-gray-400">
                Alert fires when abundance exceeds this value in any NTC.
              </p>
            </div>
          )}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Notes (optional)</label>
            <input
              type="text"
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              placeholder="e.g. Common reagent contaminant"
              className="text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-blue-300"
            />
          </div>
        </div>
        {addError && <p className="text-xs text-red-500">{addError}</p>}
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="btn-secondary">
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={adding || !lookedUp}
            className="btn-primary disabled:opacity-50"
          >
            {adding ? "Adding…" : "Add"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function NtcListsPage() {
  const navigate = useNavigate();
  const { role } = useAuth();

  const [ignoreItems, setIgnoreItems] = useState([]);
  const [contaminants, setContaminants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [addIgnoreOpen, setAddIgnoreOpen] = useState(false);
  const [addContaminantOpen, setAddContaminantOpen] = useState(false);
  const [removeTarget, setRemoveTarget] = useState(null); // { type, item }
  const [removing, setRemoving] = useState(false);

  // Inline editing for ignorelist reason
  const [editingIgnoreId, setEditingIgnoreId] = useState(null);
  const [editIgnoreText, setEditIgnoreText] = useState("");
  const [savingIgnore, setSavingIgnore] = useState(false);

  // Inline editing for contaminant min_reads
  const [editingContaminantId, setEditingContaminantId] = useState(null);
  const [editMinReads, setEditMinReads] = useState(3);
  const [savingContaminant, setSavingContaminant] = useState(false);

  useEffect(() => {
    Promise.all([getNtcIgnorelist(), getNtcContaminants()])
      .then(([ignore, contam]) => {
        setIgnoreItems(ignore);
        setContaminants(contam);
      })
      .catch(() => setError("Failed to load NTC lists."))
      .finally(() => setLoading(false));
  }, []);

  async function handleAddIgnore(id, name, sk, notes) {
    const doc = await addToNtcIgnorelist(id, name, sk, notes);
    setIgnoreItems((prev) => [doc, ...prev]);
  }

  async function handleAddContaminant(id, name, sk, notes, minReads) {
    const doc = await addNtcContaminant(id, name, sk, minReads, notes);
    setContaminants((prev) => [doc, ...prev]);
  }

  async function handleRemove() {
    setRemoving(true);
    try {
      if (removeTarget.type === "ignore") {
        await removeFromNtcIgnorelist(removeTarget.item.taxon_id);
        setIgnoreItems((prev) => prev.filter((i) => i.taxon_id !== removeTarget.item.taxon_id));
      } else {
        await removeNtcContaminant(removeTarget.item.taxon_id);
        setContaminants((prev) => prev.filter((i) => i.taxon_id !== removeTarget.item.taxon_id));
      }
      setRemoveTarget(null);
    } catch {
      alert("Failed to remove taxon.");
    } finally {
      setRemoving(false);
    }
  }

  async function saveIgnoreNote(taxonId) {
    setSavingIgnore(true);
    try {
      await updateNtcIgnorelistNote(taxonId, editIgnoreText.trim() || null);
      setIgnoreItems((prev) =>
        prev.map((i) =>
          i.taxon_id === taxonId ? { ...i, reason: editIgnoreText.trim() || null } : i
        )
      );
      setEditingIgnoreId(null);
    } catch {
      alert("Failed to save note.");
    } finally {
      setSavingIgnore(false);
    }
  }

  async function saveContaminantMinReads(taxonId) {
    setSavingContaminant(true);
    try {
      await updateNtcContaminant(taxonId, { minReads: editMinReads });
      setContaminants((prev) =>
        prev.map((c) => (c.taxon_id === taxonId ? { ...c, min_reads: editMinReads } : c))
      );
      setEditingContaminantId(null);
    } catch {
      alert("Failed to update threshold.");
    } finally {
      setSavingContaminant(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <button
          onClick={() => navigate("/ntc")}
          className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 transition-colors"
        >
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
            <path
              d="M10 3L5 8l5 5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          NTC trends
        </button>
        <span className="text-gray-200">/</span>
        <h1 className="text-sm font-medium text-gray-900 flex-1">NTC lists</h1>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-6">
        {loading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">
            Loading…
          </div>
        )}
        {error && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">{error}</div>
        )}

        {!loading && !error && (
          <>
            {/* ----------------------------------------------------------------
                Ignorelist
            ---------------------------------------------------------------- */}
            <section className="bg-white border border-gray-100 rounded-xl">
              <div className="flex items-center px-4 py-3 border-b border-gray-50">
                <div className="flex-1">
                  <h2 className="text-xs font-medium text-gray-700">Ignored taxa</h2>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Excluded from all NTC charts and calculations.
                  </p>
                </div>
                {role !== "reader" && (
                  <button onClick={() => setAddIgnoreOpen(true)} className="btn-primary">
                    + Add taxon
                  </button>
                )}
              </div>
              {ignoreItems.length === 0 ? (
                <p className="px-4 py-8 text-center text-xs text-gray-400">
                  No taxa on the ignorelist.
                </p>
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
                        ...(role !== "reader" ? [""] : []),
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
                    {ignoreItems.map((item) => (
                      <tr key={item.taxon_id} className="border-b border-gray-50">
                        <td className="px-4 py-3 text-xs text-gray-700 italic">
                          {item.taxon_name.replace(/-/g, " ")}
                        </td>
                        <td className="px-4 py-3 text-xs">
                          <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-xs">
                            {item.superkingdom ?? "—"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs font-mono text-gray-400">
                          {item.taxon_id}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-500">{item.added_by}</td>
                        <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                          {item.added_at?.slice(0, 10) ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-500 min-w-48">
                          {editingIgnoreId === item.taxon_id ? (
                            <div className="flex items-center gap-2">
                              <input
                                autoFocus
                                type="text"
                                value={editIgnoreText}
                                onChange={(e) => setEditIgnoreText(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") saveIgnoreNote(item.taxon_id);
                                  if (e.key === "Escape") setEditingIgnoreId(null);
                                }}
                                className="flex-1 text-xs border border-blue-300 rounded px-2 py-1 outline-none"
                                placeholder="Add a reason…"
                              />
                              <button
                                onClick={() => saveIgnoreNote(item.taxon_id)}
                                disabled={savingIgnore}
                                className="text-xs text-blue-500 hover:text-blue-700 disabled:opacity-50"
                              >
                                Save
                              </button>
                              <button
                                onClick={() => setEditingIgnoreId(null)}
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
                              {role !== "reader" && (
                                <button
                                  onClick={() => {
                                    setEditingIgnoreId(item.taxon_id);
                                    setEditIgnoreText(item.reason ?? "");
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
                        {role !== "reader" && (
                          <td className="px-4 py-3 text-right">
                            {role === "admin" && (
                              <button
                                onClick={() => setRemoveTarget({ type: "ignore", item })}
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

            {/* ----------------------------------------------------------------
                Known contaminants
            ---------------------------------------------------------------- */}
            <section className="bg-white border border-gray-100 rounded-xl">
              <div className="flex items-center px-4 py-3 border-b border-gray-50">
                <div className="flex-1">
                  <h2 className="text-xs font-medium text-gray-700">Known contaminants</h2>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Triggers an alert on the NTC trends page and case list when detected in any NTC
                    above the threshold.
                  </p>
                </div>
                {role !== "reader" && (
                  <button onClick={() => setAddContaminantOpen(true)} className="btn-primary">
                    + Add taxon
                  </button>
                )}
              </div>
              {contaminants.length === 0 ? (
                <p className="px-4 py-8 text-center text-xs text-gray-400">
                  No known contaminants on the list.
                </p>
              ) : (
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
                        ...(role !== "reader" ? [""] : []),
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
                    {contaminants.map((item) => (
                      <tr key={item.taxon_id} className="border-b border-gray-50">
                        <td className="px-4 py-3 text-xs text-gray-700 italic">
                          {item.taxon_name.replace(/-/g, " ")}
                        </td>
                        <td className="px-4 py-3 text-xs">
                          <span className="bg-orange-50 text-orange-700 px-2 py-0.5 rounded text-xs">
                            {item.superkingdom ?? "—"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs font-mono text-gray-400">
                          {item.taxon_id}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-600">
                          {editingContaminantId === item.taxon_id ? (
                            <div className="flex items-center gap-2">
                              <input
                                autoFocus
                                type="number"
                                min={1}
                                value={editMinReads}
                                onChange={(e) => setEditMinReads(parseInt(e.target.value) || 1)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") saveContaminantMinReads(item.taxon_id);
                                  if (e.key === "Escape") setEditingContaminantId(null);
                                }}
                                className="w-20 text-xs border border-blue-300 rounded px-2 py-1 outline-none"
                              />
                              <button
                                onClick={() => saveContaminantMinReads(item.taxon_id)}
                                disabled={savingContaminant}
                                className="text-xs text-blue-500 hover:text-blue-700 disabled:opacity-50"
                              >
                                Save
                              </button>
                              <button
                                onClick={() => setEditingContaminantId(null)}
                                className="text-xs text-gray-400 hover:text-gray-600"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 group">
                              <span className="font-mono">&gt; {item.min_reads} reads</span>
                              {role !== "reader" && (
                                <button
                                  onClick={() => {
                                    setEditingContaminantId(item.taxon_id);
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
                        {role !== "reader" && (
                          <td className="px-4 py-3 text-right">
                            {role === "admin" && (
                              <button
                                onClick={() => setRemoveTarget({ type: "contaminant", item })}
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
          </>
        )}
      </div>

      {/* Modals */}
      {addIgnoreOpen && (
        <AddTaxonModal
          title="Add to NTC ignorelist"
          showMinReads={false}
          onAdd={handleAddIgnore}
          onClose={() => setAddIgnoreOpen(false)}
        />
      )}
      {addContaminantOpen && (
        <AddTaxonModal
          title="Add known contaminant"
          showMinReads={true}
          onAdd={handleAddContaminant}
          onClose={() => setAddContaminantOpen(false)}
        />
      )}
      {removeTarget && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl border border-gray-100 shadow-lg p-6 w-80 flex flex-col gap-4">
            <p className="text-sm font-medium text-gray-900">Remove taxon?</p>
            <p className="text-xs text-gray-500">
              This will permanently remove{" "}
              <span className="italic font-medium">
                {removeTarget.item.taxon_name.replace(/-/g, " ")}
              </span>{" "}
              from the{" "}
              {removeTarget.type === "ignore" ? "NTC ignorelist" : "known contaminants list"}.
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
