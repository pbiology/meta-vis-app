import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getSamples } from "../api/samples";
import Badge from "../components/Badge";
import { fmt, fmtPct } from "../utils/format";

const FILTERS = ["All", "Samples", "Controls"];

export default function SampleList() {
  const [data, setData] = useState({ items: [], total: 0, pages: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const navigate = useNavigate();

  const filterParam = filter === "Samples" ? "sample" : filter === "Controls" ? "controls" : "";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getSamples({ page, search, filter: filterParam });
      setData(result);
    } catch {
      setError("Failed to load samples.");
    } finally {
      setLoading(false);
    }
  }, [page, search, filterParam]);

  useEffect(() => {
    load();
  }, [load]);

  function handleSearch(e) {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput);
  }

  function handleFilter(f) {
    setFilter(f);
    setPage(1);
  }

  const samples = data.items ?? [];

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100">
        <h1 className="text-sm font-medium text-gray-900 flex-1">All samples</h1>
        <form
          onSubmit={handleSearch}
          className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5 w-56"
        >
          <svg className="w-3 h-3 text-gray-400 flex-shrink-0" viewBox="0 0 16 16" fill="none">
            <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M11 11l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="Search sample ID (case sensitive)…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="bg-transparent text-xs text-gray-700 placeholder-gray-400 outline-none w-full"
          />
        </form>
      </div>

      <div className="flex gap-2 px-6 py-3 bg-white border-b border-gray-100">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => handleFilter(f)}
            className={`px-3 py-1 rounded-full text-xs transition-colors ${
              filter === f
                ? "bg-gray-900 text-white font-medium"
                : "bg-gray-100 text-gray-500 hover:bg-gray-200"
            }`}
          >
            {f}
          </button>
        ))}
        <span className="ml-auto text-xs text-gray-400 self-center">
          {data.total} sample{data.total !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="flex-1 overflow-auto">
        {loading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">
            Loading…
          </div>
        )}
        {error && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">{error}</div>
        )}
        {!loading && !error && (
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-white z-10">
              <tr>
                {[
                  "Sample ID",
                  "Order date",
                  "Case",
                  "Type",
                  "Unclassified",
                  "Species",
                  "Case status",
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
              {samples.map((s) => (
                <tr
                  key={s._id}
                  onClick={() => navigate(`/samples/${s._id}`)}
                  className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">
                    {s.sample_id ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">{s.order_date ?? "—"}</td>
                  <td className="px-4 py-3 text-xs text-gray-400 font-mono">
                    {s.case_id_str ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Badge type={s.sample_type} />
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-700">
                    {fmtPct(s.taxprofiler?.classifiers?.kraken2?.pct_unclassified)}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-700">
                    {fmt(s.taxprofiler?.classifiers?.kraken2?.num_species)}
                  </td>
                  <td className="px-4 py-3">
                    <Badge type={s.review?.reviewed ? "reviewed" : "pending"} />
                  </td>
                </tr>
              ))}
              {samples.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-sm text-gray-400">
                    No samples match this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {data.pages > 1 && (
        <div className="flex items-center justify-center gap-3 px-6 py-3 border-t border-gray-100 bg-white flex-shrink-0">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="text-xs px-3 py-1.5 border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            ← Prev
          </button>
          <span className="text-xs text-gray-400">
            Page {page} of {data.pages} · {data.total} samples
          </span>
          <button
            onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
            disabled={page === data.pages}
            className="text-xs px-3 py-1.5 border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
