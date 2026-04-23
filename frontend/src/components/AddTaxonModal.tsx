import { useState } from "react";
import { lookupTaxon } from "../utils/ncbiLookup";
import { axiosErrorDetail } from "../utils/axiosError";

interface FormState {
  taxon_id: string;
  taxon_name: string;
  superkingdom: string | null;
  notes: string;
  min_reads: number;
}

const EMPTY_FORM: FormState = {
  taxon_id: "",
  taxon_name: "",
  superkingdom: null,
  notes: "",
  min_reads: 3,
};

export interface AddTaxonModalProps {
  title: string;
  showMinReads: boolean;
  onAdd: (
    id: number,
    name: string,
    superkingdom: string | null,
    notes: string | null,
    minReads: number
  ) => Promise<void>;
  onClose: () => void;
}

export default function AddTaxonModal({ title, showMinReads, onAdd, onClose }: AddTaxonModalProps) {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [lookingUp, setLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

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
      setForm((f) => ({ ...f, taxon_name: name, superkingdom }));
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
      setAddError(axiosErrorDetail(e, "Failed to add taxon."));
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
