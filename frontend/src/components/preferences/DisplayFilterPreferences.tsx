import { Link } from "react-router-dom";
import { useTaxonLists } from "../../hooks/queries/useTaxonLists";

interface DisplayFilterPreferencesProps {
  selected: string[];
  onToggle: (listId: string) => void;
}

/**
 * Which display-filter lists hide taxa from the user's taxonomy tables — the
 * same `active_display_filters` preference as the table's "Hide lists" menu.
 */
export default function DisplayFilterPreferences({
  selected,
  onToggle,
}: Readonly<DisplayFilterPreferencesProps>) {
  const listsQ = useTaxonLists("display_filter");
  const lists = listsQ.data ?? [];

  return (
    <div className="bg-white border border-gray-100 rounded-xl p-5">
      <h2 className="text-sm font-medium text-gray-800 mb-1">Hidden taxa (display filters)</h2>
      <p className="text-xs text-gray-400 mb-4">
        Taxa on the lists you tick are hidden from the taxonomy table on sample and case pages.
        Display only: read totals, reports and alerts are unaffected, and known pathogens are never
        hidden. You can pause the filters on any table with <em>Show all</em>.
      </p>
      {listsQ.isLoading && <p className="text-xs text-gray-400">Loading…</p>}
      {listsQ.isError && <p className="text-xs text-red-500">Failed to load display filters.</p>}
      {!listsQ.isLoading && !listsQ.isError && lists.length === 0 && (
        <p className="text-xs text-gray-400">No display filters yet.</p>
      )}
      {lists.length > 0 && (
        <div className="flex flex-col gap-2">
          {lists.map((list) => (
            <label
              key={list.list_id}
              className="flex items-center gap-2.5 cursor-pointer select-none"
            >
              <input
                type="checkbox"
                checked={selected.includes(list.list_id)}
                onChange={() => onToggle(list.list_id)}
                className="rounded"
              />
              <span className="text-xs text-gray-700 flex-1">{list.name}</span>
              <span className="text-xs text-gray-400">
                {list.entry_count.toLocaleString()} taxa
              </span>
            </label>
          ))}
        </div>
      )}
      <Link
        to="/display-filters"
        className="inline-block mt-4 text-xs text-blue-600 hover:text-blue-800"
      >
        Manage display filters
      </Link>
    </div>
  );
}
