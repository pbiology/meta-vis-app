import { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useAddToIgnorelist, useIgnorelist, useOutbreaks } from "../hooks/queries/useAlerts";
import { useAuth } from "../context/AuthContext";
import { multiAnalysisFilter } from "../lib/analysisPreference";
import type { Outbreak } from "../api/types";

export default function Alerts() {
  const navigate = useNavigate();
  const { role, preferences } = useAuth();
  const location = useLocation();
  const visibleAnalysis = preferences?.visible_analysis_types;

  const [windowDays, setWindowDays] = useState(14);
  const [highlightedId, setHighlightedId] = useState<number | null>(null);
  const sectionRefs = useRef<Record<number, HTMLElement | null>>({});

  const analysisTypes = multiAnalysisFilter(visibleAnalysis);
  const outbreaksQ = useOutbreaks(windowDays, analysisTypes);
  const ignorelistQ = useIgnorelist();
  const addToIgnoreMutation = useAddToIgnorelist();

  const data = outbreaksQ.data ?? null;
  const ignorelist = ignorelistQ.data ?? [];
  const isLoading = outbreaksQ.isLoading || ignorelistQ.isLoading;
  const isError = outbreaksQ.isError || ignorelistQ.isError;

  useEffect(() => {
    if (!data || !location.hash) return;
    const taxonId = parseInt(location.hash.replace("#taxon-", ""));
    if (!taxonId) return;
    setHighlightedId(taxonId);
    setTimeout(() => {
      const el = sectionRefs.current[taxonId];
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);
  }, [data, location.hash]);

  async function handleIgnore(outbreak: Outbreak) {
    try {
      const superkingdom = outbreak.superkingdoms?.[0] || "Viruses";
      await addToIgnoreMutation.mutateAsync({
        taxonId: outbreak.taxon_id,
        taxonName: outbreak.taxon_name,
        superkingdom,
      });
    } catch {
      alert("Failed to add taxon to ignorelist.");
    }
  }

  const outbreaks = data?.outbreaks || [];
  const ignored = new Set(ignorelist.map((i) => i.taxon_id));
  const ignoringTaxonId = addToIgnoreMutation.isPending
    ? (addToIgnoreMutation.variables?.taxonId ?? null)
    : null;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <h1 className="text-sm font-medium text-gray-900 flex-1">Outbreak alerts</h1>
        <Link
          to="/alerts/ignorelist"
          className="flex items-center gap-1.5 text-xs border border-gray-200 rounded-lg px-3 py-1.5 text-gray-500 hover:bg-gray-50 transition-colors"
        >
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.3" />
            <path d="M5 8h6M8 5v6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          Ignored taxa
          {ignorelist.length > 0 && (
            <span className="bg-gray-100 text-gray-500 text-xs px-1.5 py-0.5 rounded-full font-medium">
              {ignorelist.length}
            </span>
          )}
        </Link>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Window</span>
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setWindowDays(d)}
              className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                windowDays === d
                  ? "bg-gray-900 text-white font-medium"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-4">
        {isLoading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">
            Loading…
          </div>
        )}
        {isError && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">
            Failed to load outbreak alerts.
          </div>
        )}
        {!isLoading && !isError && outbreaks.length === 0 && (
          <div className="flex flex-col items-center justify-center h-40 gap-2">
            <svg className="w-8 h-8 text-green-300" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" />
              <path
                d="M8 12l3 3 5-5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <p className="text-sm text-gray-400">
              No outbreak signals detected in the last {windowDays} days.
            </p>
          </div>
        )}

        {!isLoading &&
          !isError &&
          outbreaks.map((outbreak) => (
            <section
              key={`${outbreak.taxon_id}-${outbreak.config_name}`}
              id={`taxon-${outbreak.taxon_id}`}
              ref={(el) => {
                sectionRefs.current[outbreak.taxon_id] = el;
              }}
              className={`bg-white border rounded-xl transition-colors duration-500 ${
                highlightedId === outbreak.taxon_id
                  ? "border-amber-400 ring-2 ring-amber-200"
                  : "border-amber-100"
              }`}
            >
              <div className="flex items-center gap-3 px-4 py-3 border-b border-amber-50">
                <svg
                  className="w-3.5 h-3.5 text-amber-500 flex-shrink-0"
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
                <div className="flex-1">
                  <p className="text-xs font-medium text-gray-700 italic">
                    {outbreak.taxon_name.replace(/-/g, " ")}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">{outbreak.config_name}</p>
                </div>
                <span className="text-xs text-amber-600 font-medium mr-2">
                  {outbreak.case_ids.length} cases · {windowDays}d window
                </span>
                {role !== "reader" && (
                  <button
                    onClick={() => handleIgnore(outbreak)}
                    disabled={
                      ignoringTaxonId === outbreak.taxon_id || ignored.has(outbreak.taxon_id)
                    }
                    className="text-xs text-gray-400 hover:text-gray-600 border border-gray-200 rounded-lg px-2.5 py-1 transition-colors disabled:opacity-50"
                  >
                    {ignoringTaxonId === outbreak.taxon_id
                      ? "Ignoring…"
                      : ignored.has(outbreak.taxon_id)
                        ? "Ignored"
                        : "Ignore"}
                  </button>
                )}
              </div>
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr>
                    {["Case", "Order date"].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-2 text-xs font-medium text-gray-400 border-b border-gray-50"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...outbreak.cases]
                    .sort((a, b) => (a.order_date ?? "").localeCompare(b.order_date ?? ""))
                    .map((c) => (
                      <tr
                        key={c.case_id}
                        onClick={() => navigate(`/cases/${c.case_id}`)}
                        className="cursor-pointer border-b border-gray-50 hover:bg-amber-50 transition-colors"
                      >
                        <td className="px-4 py-2.5 font-mono text-xs text-gray-700">{c.case_id}</td>
                        <td className="px-4 py-2.5 text-xs text-gray-500">{c.order_date ?? "—"}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </section>
          ))}
      </div>
    </div>
  );
}
