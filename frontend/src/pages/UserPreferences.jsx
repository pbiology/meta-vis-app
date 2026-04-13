import { useState } from "react";
import { useAuth } from "../context/AuthContext";

const KINGDOMS = ["Bacteria", "Viruses", "Eukaryota", "Archaea"];

export default function UserPreferences() {
  const { preferences, setPreferences } = useAuth();
  const [selected, setSelected] = useState(preferences?.preferred_kingdoms ?? ["Viruses"]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await setPreferences({ preferred_kingdoms: selected });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      setError("Failed to save preferences.");
    } finally {
      setSaving(false);
    }
  }

  function toggle(kingdom) {
    setSelected((prev) =>
      prev.includes(kingdom) ? prev.filter((k) => k !== kingdom) : [...prev, kingdom],
    );
    setSaved(false);
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-lg">
        <h1 className="text-xl font-semibold text-gray-900 mb-1">Preferences</h1>
        <p className="text-sm text-gray-500 mb-8">
          These settings apply to your account and persist across sessions.
        </p>

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
                  checked={selected.includes(k)}
                  onChange={() => toggle(k)}
                  className="rounded"
                />
                <span className="text-sm text-gray-700">{k}</span>
              </label>
            ))}
          </div>

          <div className="flex items-center gap-3 mt-5">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-1.5 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            {saved && <span className="text-xs text-green-600">Saved</span>}
            {error && <span className="text-xs text-red-500">{error}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
