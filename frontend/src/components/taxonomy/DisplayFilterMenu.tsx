import { useState } from "react";
import { Link } from "react-router-dom";
import type { TaxonListSummary } from "../../api/types";

interface DisplayFilterMenuProps {
  lists: TaxonListSummary[];
  activeIds: string[];
  onChange: (next: string[]) => Promise<void>;
}

/** Dropdown for choosing which display-filter lists hide taxa in the table. */
export default function DisplayFilterMenu({
  lists,
  activeIds,
  onChange,
}: Readonly<DisplayFilterMenuProps>) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  async function toggle(listId: string, checked: boolean) {
    const next = checked ? [...activeIds, listId] : activeIds.filter((id) => id !== listId);
    setSaving(true);
    try {
      await onChange(next);
    } catch {
      alert("Failed to save display filters.");
    } finally {
      setSaving(false);
    }
  }

  const active = activeIds.length > 0;
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`text-xs border rounded-lg px-3 py-1.5 bg-white flex items-center gap-1.5 transition-colors ${
          active ? "border-blue-300 text-blue-600" : "border-gray-200 text-gray-500"
        }`}
      >
        {active ? `Hide lists (${activeIds.length})` : "Hide lists"}
        <svg
          className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`}
          viewBox="0 0 16 16"
          fill="none"
        >
          <path
            d="M4 6l4 4 4-4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-1 bg-white border border-gray-100 rounded-xl shadow-lg z-20 min-w-56 py-1">
          {lists.length === 0 && (
            <p className="px-3 py-1.5 text-xs text-gray-400">No display filters yet.</p>
          )}
          {lists.map((list) => (
            <label
              key={list.list_id}
              className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer"
            >
              <input
                type="checkbox"
                checked={activeIds.includes(list.list_id)}
                disabled={saving}
                onChange={(e) => toggle(list.list_id, e.target.checked)}
                className="rounded"
              />
              <span className="text-xs text-gray-600 flex-1">{list.name}</span>
              <span className="text-xs text-gray-300">{list.entry_count}</span>
            </label>
          ))}
          <Link
            to="/display-filters"
            className="block px-3 py-1.5 text-xs text-gray-400 hover:text-gray-600 border-t border-gray-50 mt-1"
          >
            Manage lists…
          </Link>
        </div>
      )}
    </div>
  );
}
