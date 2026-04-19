import { useState } from "react";
import { useAuth } from "../context/AuthContext";

const KINGDOMS = ["Bacteria", "Viruses", "Eukaryota", "Archaea"];

const ANALYSIS_TYPES = [
  {
    key: "shotgun",
    label: "Shotgun metagenomics",
    hint: "Taxprofiler (incl. Metaval)",
  },
  {
    key: "amplicon",
    label: "Amplicon metagenomics",
    hint: "TRANA",
  },
];

export default function UserPreferences() {
  const { preferences, setPreferences } = useAuth();
  const [selectedKingdoms, setSelectedKingdoms] = useState(
    preferences?.preferred_kingdoms ?? ["Viruses"]
  );
  const [selectedAnalysis, setSelectedAnalysis] = useState(
    preferences?.visible_analysis_types ?? ["shotgun", "amplicon"]
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  const analysisEmpty = selectedAnalysis.length === 0;

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await setPreferences({
        preferred_kingdoms: selectedKingdoms,
        visible_analysis_types: selectedAnalysis,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      setError("Failed to save preferences.");
    } finally {
      setSaving(false);
    }
  }

  function toggleKingdom(kingdom) {
    setSelectedKingdoms((prev) =>
      prev.includes(kingdom) ? prev.filter((k) => k !== kingdom) : [...prev, kingdom]
    );
    setSaved(false);
  }

  function toggleAnalysis(key) {
    setSelectedAnalysis((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
    setSaved(false);
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-lg flex flex-col gap-5">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 mb-1">Preferences</h1>
          <p className="text-sm text-gray-500">
            These settings apply to your account and persist across sessions.
          </p>
        </div>

        <div className="bg-white border border-gray-100 rounded-xl p-5">
          <h2 className="text-sm font-medium text-gray-800 mb-1">Default taxonomy kingdoms</h2>
          <p className="text-xs text-gray-400 mb-4">
            The taxonomy table on sample pages will start with these kingdoms selected. You can
            still change the filter temporarily while viewing a sample.
          </p>
          <div className="flex flex-col gap-2">
            {KINGDOMS.map((k) => (
              <label key={k} className="flex items-center gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={selectedKingdoms.includes(k)}
                  onChange={() => toggleKingdom(k)}
                  className="rounded"
                />
                <span className="text-sm text-gray-700">{k}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="bg-white border border-gray-100 rounded-xl p-5">
          <h2 className="text-sm font-medium text-gray-800 mb-1">Visible analysis types</h2>
          <p className="text-xs text-gray-400 mb-4">
            Hide analysis types you do not work with. Cases, samples, outbreak alerts and NTC trends
            will only show the types you keep enabled. At least one must remain selected.
          </p>
          <div className="flex flex-col gap-2">
            {ANALYSIS_TYPES.map((a) => (
              <label key={a.key} className="flex items-center gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={selectedAnalysis.includes(a.key)}
                  onChange={() => toggleAnalysis(a.key)}
                  className="rounded"
                />
                <span className="text-sm text-gray-700">
                  {a.label}
                  <span className="text-gray-400 ml-1.5">({a.hint})</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving || analysisEmpty}
            className="px-4 py-1.5 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
          >
            {saving ? "Saving…" : "Save"}
          </button>
          {saved && <span className="text-xs text-green-600">Saved</span>}
          {analysisEmpty && (
            <span className="text-xs text-amber-600">Select at least one analysis type.</span>
          )}
          {error && <span className="text-xs text-red-500">{error}</span>}
        </div>
      </div>
    </div>
  );
}
