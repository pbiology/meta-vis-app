import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getIgnorelist, removeFromIgnorelist, updateIgnorelistNote } from "../api/alerts";
import { useAuth } from "../context/AuthContext";

export default function IgnoreList() {
  const navigate = useNavigate();
  const { role } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState("");
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState(null); // null, 'Viruses', 'Bacteria', etc.

  useEffect(() => {
    getIgnorelist(filter)
      .then(setItems)
      .catch(() => setError("Failed to load ignorelist."))
      .finally(() => setLoading(false));
  }, [filter]);

  async function handleRemove(taxonId) {
    try {
      await removeFromIgnorelist(taxonId);
      setItems((prev) => prev.filter((i) => i.taxon_id !== taxonId));
    } catch {
      alert("Failed to remove taxon.");
    }
  }

  function startEdit(item) {
    setEditingId(item.taxon_id);
    setEditText(item.reason ?? "");
  }

  async function saveEdit(taxonId) {
    setSaving(true);
    try {
      await updateIgnorelistNote(taxonId, editText.trim() || null);
      setItems((prev) =>
        prev.map((i) => (i.taxon_id === taxonId ? { ...i, reason: editText.trim() || null } : i))
      );
      setEditingId(null);
    } catch {
      alert("Failed to save note.");
    } finally {
      setSaving(false);
    }
  }

  // Get unique superkingdoms from items
  const superkingdoms = [...new Set(items.map((i) => i.superkingdom))].filter(Boolean).sort();

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <button
          onClick={() => navigate("/alerts")}
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
          Alerts
        </button>
        <span className="text-gray-200">/</span>
        <h1 className="text-sm font-medium text-gray-900 flex-1">Ignored taxa</h1>

        {superkingdoms.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Filter</span>
            <button
              onClick={() => setFilter(null)}
              className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                filter === null
                  ? "bg-gray-900 text-white font-medium"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              All
            </button>
            {superkingdoms.map((sk) => (
              <button
                key={sk}
                onClick={() => setFilter(sk)}
                className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                  filter === sk
                    ? "bg-gray-900 text-white font-medium"
                    : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                }`}
              >
                {sk}
              </button>
            ))}
          </div>
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
                {filter ? `No ${filter} taxa on the ignorelist.` : "No taxa on the ignorelist."}
              </p>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr>
                    {[
                      "Taxon",
                      "Type",
                      "Tax ID",
                      "Ignored by",
                      "Date added to list",
                      "Notes",
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
                        <span className="bg-gray-100 text-gray-700 px-2 py-0.5 rounded text-xs font-medium">
                          {item.superkingdom}
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
                              placeholder="Add a note…"
                            />
                            <button
                              onClick={() => saveEdit(item.taxon_id)}
                              disabled={saving}
                              className="text-xs text-blue-500 hover:text-blue-700 transition-colors disabled:opacity-50"
                            >
                              Save
                            </button>
                            <button
                              onClick={() => setEditingId(null)}
                              className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2 group">
                            <span className={item.reason ? "" : "text-gray-300"}>
                              {item.reason ?? "No notes"}
                            </span>
                            {role !== "reader" && (
                              <button
                                onClick={() => startEdit(item)}
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
                              onClick={() => handleRemove(item.taxon_id)}
                              className="text-xs text-gray-400 hover:text-red-500 transition-colors"
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
        )}
      </div>
    </div>
  );
}
