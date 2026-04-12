import { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getCases, deleteCase, getCaseStats, getPathogenCases } from "../api/cases";
import Badge from "../components/Badge";
import { getOutbreaks } from "../api/alerts";
import { getNtcContaminantCaseIds } from "../api/ntc";
import { useAuth } from "../context/AuthContext";

export default function CaseList() {
  const [data, setData] = useState({ items: [], total: 0, pages: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [outbreakCaseIds, setOutbreakCaseIds] = useState(new Set());
  const [pathogenCaseIds, setPathogenCaseIds] = useState(new Set());
  const [ntcContaminantCaseIds, setNtcContaminantCaseIds] = useState(new Set());
  const [stats, setStats] = useState({ total: 0, pending: 0, reviewed: 0 });
  const navigate = useNavigate();
  const { role } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const filter = searchParams.get("filter") ?? "all";

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      setError(null);
      try {
        const result = await getCases({ page, search, reviewed: filter });
        setData(result);
        getOutbreaks(14)
          .then((d) => setOutbreakCaseIds(new Set(d.outbreaks.flatMap((o) => o.case_ids))))
          .catch(() => {});
        getPathogenCases()
          .then((d) => setPathogenCaseIds(new Set(d.case_ids)))
          .catch(() => {});
        getNtcContaminantCaseIds()
          .then((d) => setNtcContaminantCaseIds(new Set(d.case_ids)))
          .catch(() => {});
      } catch {
        setError("Failed to load cases.");
      } finally {
        getPathogenCases()
          .then((d) => setPathogenCaseIds(new Set(d.case_ids)))
          .catch(() => {});
        getNtcContaminantCaseIds()
          .then((d) => setNtcContaminantCaseIds(new Set(d.case_ids)))
          .catch(() => {});
        setLoading(false);
      }
    },
    [page, search, filter]
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    getCaseStats()
      .then(setStats)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      load(true);
      getCaseStats()
        .then(setStats)
        .catch(() => {});
    }, 30_000);
    return () => clearInterval(interval);
  }, [load]);

  function handleSearch(e) {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput);
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await deleteCase(deleteTarget);
      setDeleteTarget(null);
      load();
      getCaseStats()
        .then(setStats)
        .catch(() => {});
    } catch {
      alert("Failed to delete case.");
    } finally {
      setDeleting(false);
    }
  }

  const cases = data.items ?? [];

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100">
        <h1 className="text-sm font-medium text-gray-900 flex-1">Cases</h1>
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
            placeholder="Search case name (case sensitive)…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="bg-transparent text-xs text-gray-700 placeholder-gray-400 outline-none w-full"
          />
        </form>
        <div className="flex items-center gap-2 border-l border-gray-200 pl-3">
          {["all", "pending", "reviewed"].map((f) => (
            <button
              key={f}
              onClick={() => {
                setPage(1);
                setSearchParams(f === "all" ? {} : { filter: f });
              }}
              className={`text-xs font-medium px-2.5 py-1.5 rounded-md transition-colors ${
                filter === f ? "bg-blue-100 text-blue-700" : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              {f === "all" && <>All Cases</>}
              {f === "pending" && <>Pending</>}
              {f === "reviewed" && <>Reviewed</>}
            </button>
          ))}
        </div>
        <div className="ml-auto pl-3 border-l border-gray-200 flex items-center gap-4">
          <span className="text-xs text-gray-400">
            <span className="text-amber-500 font-medium">{stats.pending}</span> pending
          </span>
          <span className="text-xs text-gray-400">
            <span className="text-green-600 font-medium">{stats.reviewed}</span> reviewed
          </span>
          <span className="text-xs text-gray-300">{stats.total} total</span>
        </div>
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
                  "Case name",
                  "Date",
                  "Samples",
                  "Sample names",
                  "Notes",
                  "Status",
                  "Reviewed by",
                  "",
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
              {cases.map((c) => (
                <tr
                  key={c._id}
                  onClick={() => navigate(`/cases/${c.case_id}`)}
                  className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">
                    <div className="flex items-center gap-1.5">
                      {c.case_id}
                      {outbreakCaseIds.has(c._id) && (
                        <svg
                          className="w-3 h-3 text-amber-500 flex-shrink-0"
                          viewBox="0 0 16 16"
                          fill="none"
                        >
                          <path
                            d="M8 2L14 13H2L8 2z"
                            stroke="currentColor"
                            strokeWidth="1.3"
                            strokeLinejoin="round"
                          />
                          <path
                            d="M8 6v3M8 11v.5"
                            stroke="currentColor"
                            strokeWidth="1.3"
                            strokeLinecap="round"
                          />
                        </svg>
                      )}
                      {pathogenCaseIds.has(c._id) && (
                        <svg
                          className="w-3 h-3 text-red-500 flex-shrink-0"
                          viewBox="0 0 16 16"
                          fill="none"
                          title="Contains known pathogen"
                        >
                          <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.3" />
                          <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.3" />
                          <path
                            d="M8 2.5v1.5M8 12v1.5M2.5 8h1.5M12 8h1.5"
                            stroke="currentColor"
                            strokeWidth="1.3"
                            strokeLinecap="round"
                          />
                        </svg>
                      )}
                      {ntcContaminantCaseIds.has(c._id) && (
                        <svg
                          className="w-3 h-3 text-orange-500 flex-shrink-0"
                          viewBox="0 0 16 16"
                          fill="none"
                          title="NTC contains known contaminant"
                        >
                          <path
                            d="M8 3a3 3 0 0 1 3 3v1.5h.5a1 1 0 0 1 1 1V13a1 1 0 0 1-1 1H4.5a1 1 0 0 1-1-1V8.5a1 1 0 0 1 1-1H5V6a3 3 0 0 1 3-3z"
                            stroke="currentColor"
                            strokeWidth="1.3"
                            strokeLinejoin="round"
                          />
                          <circle cx="8" cy="10.5" r="0.75" fill="currentColor" />
                        </svg>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {c.order_date ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {c.sample_count ?? 0} sample{(c.sample_count ?? 0) !== 1 ? "s" : ""}
                    {(c.control_count ?? 0) > 0 && (
                      <span className="text-gray-300 ml-1">+{c.control_count} ctrl</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-600" style={{ maxWidth: "220px" }}>
                    <span className="block truncate" title={(c.sample_names ?? []).join(", ")}>
                      {(c.sample_names ?? []).join(", ") || "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {(c.notes?.length ?? 0) > 0 ? (
                      <span className="text-amber-600 font-medium">{c.notes.length}</span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Badge type={c.review?.reviewed ? "reviewed" : "pending"} />
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {c.review?.reviewed_by ?? "—"}
                  </td>
                  {role === "admin" && (
                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => setDeleteTarget(c.case_id)}
                        className="text-xs text-gray-300 hover:text-red-500 transition-colors"
                      >
                        Delete
                      </button>
                    </td>
                  )}
                </tr>
              ))}
              {cases.length === 0 && (
                <tr>
                  <td
                    colSpan={role === "admin" ? 8 : 7}
                    className="px-4 py-10 text-center text-sm text-gray-400"
                  >
                    No cases found.
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
            Page {page} of {data.pages} · {data.total} cases
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

      {deleteTarget && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl border border-gray-100 shadow-lg p-6 w-80 flex flex-col gap-4">
            <p className="text-sm font-medium text-gray-900">Delete case?</p>
            <p className="text-xs text-gray-500">
              This will permanently delete{" "}
              <span className="font-mono font-medium">{deleteTarget}</span> and all associated
              samples, Krona files, and metaval results. This cannot be undone.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteTarget(null)} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-3 py-1.5 text-xs font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deleting ? "Deleting…" : "Delete case"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
