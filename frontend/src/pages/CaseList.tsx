import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useCases, useCaseStats, useDeleteCase, usePathogenCases } from "../hooks/queries/useCases";
import { useOutbreaks } from "../hooks/queries/useAlerts";
import { useNtcContaminantCaseIds } from "../hooks/queries/useNtc";
import type { ReviewedFilter } from "../api/cases";
import Badge from "../components/Badge";
import { useAuth } from "../context/AuthContext";
import { singleAnalysisFilter } from "../lib/analysisPreference";

const POLL_MS = 30_000;

export default function CaseList() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const { role, preferences, preferencesLoaded } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const filter = searchParams.get("filter") ?? "all";
  const analysisFilter = searchParams.get("analysis") ?? "all";
  const visibleAnalysis = preferences?.visible_analysis_types;
  const effectiveAnalysis = singleAnalysisFilter(visibleAnalysis, analysisFilter) ?? "all";

  const casesQ = useCases(
    {
      page,
      search,
      reviewed: filter as ReviewedFilter,
      analysisType: effectiveAnalysis,
    },
    { refetchInterval: preferencesLoaded ? POLL_MS : undefined }
  );
  const statsQ = useCaseStats({ refetchInterval: POLL_MS });
  const outbreaksQ = useOutbreaks(14);
  const pathogenCasesQ = usePathogenCases();
  const ntcCaseIdsQ = useNtcContaminantCaseIds();
  const deleteMutation = useDeleteCase();

  const data = casesQ.data ?? { items: [], total: 0, pages: 1, ticket_links_enabled: false };
  const stats = statsQ.data ?? { total: 0, pending: 0, reviewed: 0 };
  const visibleAnalysisTypes = visibleAnalysis ?? ["shotgun", "amplicon"];
  const showShotgun = visibleAnalysisTypes.includes("shotgun");
  const showAmplicon = visibleAnalysisTypes.includes("amplicon");
  const pendingShotgun = (stats.pending_shotgun as number | undefined) ?? 0;
  const pendingAmplicon = (stats.pending_amplicon as number | undefined) ?? 0;
  const outbreakCaseIds = new Set(outbreaksQ.data?.outbreaks.flatMap((o) => o.case_ids) ?? []);
  const pathogenCaseIds = new Set(pathogenCasesQ.data?.case_ids ?? []);
  const ntcContaminantCaseIds = new Set(ntcCaseIdsQ.data?.case_ids ?? []);

  function handleSearch(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput);
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget);
      setDeleteTarget(null);
    } catch {
      alert("Failed to delete case.");
    }
  }

  const cases = data.items ?? [];
  const ticketLinksEnabled = data.ticket_links_enabled ?? false;
  const isLoading = casesQ.isLoading;
  const isError = casesQ.isError;

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
                const next = new URLSearchParams(searchParams);
                if (f === "all") next.delete("filter");
                else next.set("filter", f);
                setSearchParams(next);
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
        {(visibleAnalysis?.length ?? 2) !== 1 && (
          <div className="flex items-center gap-2 border-l border-gray-200 pl-3">
            {["all", "shotgun", "amplicon"].map((a) => (
              <button
                key={a}
                onClick={() => {
                  setPage(1);
                  const next = new URLSearchParams(searchParams);
                  if (a === "all") next.delete("analysis");
                  else next.set("analysis", a);
                  setSearchParams(next);
                }}
                className={`text-xs font-medium px-2.5 py-1.5 rounded-md transition-colors ${
                  analysisFilter === a
                    ? "bg-blue-100 text-blue-700"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                {a === "all" && <>All Types</>}
                {a === "shotgun" && <>Shotgun</>}
                {a === "amplicon" && <>Amplicon</>}
              </button>
            ))}
          </div>
        )}
        <div className="ml-auto pl-3 border-l border-gray-200 flex items-center gap-4">
          <span className="text-xs text-gray-400">
            <span className="text-amber-500 font-medium">{String(stats.pending ?? 0)}</span> pending
          </span>
          <span className="text-xs text-gray-400">
            <span className="text-green-600 font-medium">{String(stats.reviewed ?? 0)}</span>{" "}
            reviewed
          </span>
          <span className="text-xs text-gray-300">{String(stats.total ?? 0)} total</span>
        </div>
      </div>

      <div className="px-4 py-3 bg-amber-50/50 border-b border-gray-100 text-lg text-gray-600 flex items-center gap-6">
        <span className="font-medium text-gray-700">Ready for review:</span>
        {showShotgun && (
          <span>
            <span className="text-amber-600 font-semibold">{pendingShotgun}</span> shotgun
          </span>
        )}
        {showAmplicon && (
          <span>
            <span className="text-amber-600 font-semibold">{pendingAmplicon}</span> amplicon
          </span>
        )}
      </div>

      <div className="flex-1 overflow-auto">
        {isLoading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">
            Loading…
          </div>
        )}
        {isError && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">
            Failed to load cases.
          </div>
        )}
        {!isLoading && !isError && (
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-white z-10">
              <tr>
                {[
                  "Case name",
                  ...(ticketLinksEnabled ? ["Ticket"] : []),
                  "Date",
                  "Analysis",
                  "Platform",
                  "Samples",
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
                  key={c.case_id}
                  onClick={() =>
                    window.open(`/cases/${c.case_id}`, "_blank", "noopener,noreferrer")
                  }
                  className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">
                    <div className="flex items-center gap-1.5">
                      {c.case_id}
                      {outbreakCaseIds.has(c.case_id) && (
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
                      {pathogenCaseIds.has(c.case_id) && (
                        <svg
                          className="w-3 h-3 text-red-500 flex-shrink-0"
                          viewBox="0 0 16 16"
                          fill="none"
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
                      {ntcContaminantCaseIds.has(c.case_id) && (
                        <svg
                          className="w-3 h-3 text-orange-500 flex-shrink-0"
                          viewBox="0 0 16 16"
                          fill="none"
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
                  {ticketLinksEnabled && (
                    <td
                      className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {c.ticket_url ? (
                        <a
                          href={c.ticket_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          {c.ticket_id}
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                  )}
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {c.order_date ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {c.analysis_type === "shotgun"
                      ? "Shotgun"
                      : c.analysis_type === "amplicon"
                        ? "Amplicon"
                        : "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {c.sequencing_platform
                      ? c.sequencing_platform.charAt(0).toUpperCase() +
                        c.sequencing_platform.slice(1)
                      : "—"}
                  </td>
                  <td
                    className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap"
                    title={(c.sample_names ?? []).join(", ") || undefined}
                  >
                    {c.sample_count ?? 0} sample{(c.sample_count ?? 0) !== 1 ? "s" : ""}
                    {(c.control_count ?? 0) > 0 && (
                      <span className="text-gray-300 ml-1">+{c.control_count} ctrl</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {(c.notes?.length ?? 0) > 0 ? (
                      <span className="text-amber-600 font-medium">{c.notes?.length}</span>
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
                    colSpan={role === "admin" ? 9 : 8}
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
                disabled={deleteMutation.isPending}
                className="px-3 py-1.5 text-xs font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deleteMutation.isPending ? "Deleting…" : "Delete case"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
