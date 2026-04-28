import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useAppConfig } from "../context/ConfigContext";
import KingdomBadge from "./KingdomBadge";
import { fmt, fmtPct } from "../utils/format";
import type { SampleProfile, SampleProfileEntry } from "../api/types";

const SESSION_KEY = "taxonomy-filters";

interface TaxFilters {
  taxSearch: string;
  kingdoms: string[];
  concordanceMin: number;
  metavalOnly: boolean;
}

function loadFilters(): Partial<TaxFilters> {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY) ?? "{}") as Partial<TaxFilters>;
  } catch {
    return {};
  }
}

function saveFilters(patch: Partial<TaxFilters>) {
  try {
    const current = loadFilters();
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ ...current, ...patch }));
  } catch {
    // sessionStorage unavailable — silently skip
  }
}

export interface MetavalResultRef {
  _id: string;
  taxon_id: number;
  classifier: string;
}

export interface NtcProfileForClassifier {
  sample_id: string;
  classifiers?: Record<string, Record<number, number>>;
}

export interface ContaminantConfig {
  threshold?: number;
  eligible_ranks?: string[];
}

export interface ClfQc {
  classified_reads?: number;
  unclassified_reads?: number;
  total_reads?: number;
  queries_aligned?: number;
  [key: string]: unknown;
}

interface TaxonomyTableProps {
  profile: SampleProfile;
  allProfiles?: SampleProfile[];
  clfQc?: ClfQc | null;
  metavalResults: MetavalResultRef[];
  sampleId: string;
  outbreakTaxonIds: Set<number>;
  ntcProfiles: NtcProfileForClassifier[];
  contaminantConfig?: ContaminantConfig | null;
  pathogenIds?: Set<number>;
  abundanceIsFraction?: boolean;
  isNtc?: boolean;
}

type SortCol = "name" | "rank" | "superkingdom" | "abundance" | "ntc" | "concordance";

interface SortState {
  col: SortCol;
  dir: 1 | -1;
}

export default function TaxonomyTable({
  profile,
  allProfiles,
  clfQc,
  metavalResults,
  sampleId,
  outbreakTaxonIds,
  ntcProfiles,
  contaminantConfig,
  pathogenIds,
  abundanceIsFraction = false,
  isNtc = false,
}: TaxonomyTableProps) {
  const { sessionKingdoms, setSessionKingdoms } = useAuth();
  const { hostTaxonIds } = useAppConfig();

  const saved = loadFilters();
  const [taxSearch, setTaxSearch] = useState(() => saved.taxSearch ?? "");
  const [taxKingdoms, setTaxKingdoms] = useState<string[]>(() => saved.kingdoms ?? sessionKingdoms);
  const [taxSort, setTaxSort] = useState<SortState>({ col: "abundance", dir: -1 });
  const [taxPage, setTaxPage] = useState(0);
  const [metavalOnly, setMetavalOnly] = useState(() => saved.metavalOnly ?? false);
  const [kingdomOpen, setKingdomOpen] = useState(false);
  const [concordanceMin, setConcordanceMin] = useState(() => saved.concordanceMin ?? 1);
  const TAX_PER_PAGE = 50;

  const allClassifierNames = (allProfiles ?? []).map((p) => p.classifier);
  const concordanceMap: Record<number, Set<string>> = {};
  for (const p of allProfiles ?? []) {
    for (const entry of p.profile ?? []) {
      if (entry.abundance >= concordanceMin) {
        if (!concordanceMap[entry.taxon_id]) concordanceMap[entry.taxon_id] = new Set();
        concordanceMap[entry.taxon_id].add(p.classifier);
      }
    }
  }

  const allEntries = profile?.profile ?? [];
  const hostReads = allEntries.find((t) => t.taxon_id === 9606)?.abundance ?? 0;
  const unclassReads = allEntries.find((t) => t.taxon_id === 0)?.abundance ?? 0;
  const rootReads = allEntries.find((t) => t.taxon_id === 1)?.abundance ?? 0;
  const classifiedReads = clfQc?.classified_reads ?? rootReads;
  const totalReads = unclassReads + classifiedReads;
  const nonHostTotal =
    classifiedReads > 0
      ? classifiedReads - hostReads
      : allEntries
          .filter(
            (t) =>
              !hostTaxonIds.has(t.taxon_id) &&
              t.name !== "unclassified" &&
              !t.name?.startsWith("unclassified ")
          )
          .reduce((sum, t) => sum + t.abundance, 0);

  const ntcForClassifier = ntcProfiles.map((ntc) => ({
    sample_id: ntc.sample_id,
    abundanceMap: ntc.classifiers?.[profile.classifier] ?? {},
  }));
  const showNtcColumn = !isNtc;
  const hasNtc = showNtcColumn && ntcForClassifier.length > 0;

  const tableEntries = allEntries.filter(
    (t) =>
      !hostTaxonIds.has(t.taxon_id) &&
      t.name !== "unclassified" &&
      !t.name?.startsWith("unclassified ")
  );

  const filtered = tableEntries.filter((t) => {
    if (taxSearch && !t.name?.toLowerCase().includes(taxSearch.toLowerCase())) return false;
    if (taxKingdoms.length > 0 && !taxKingdoms.includes(t.superkingdom ?? "")) return false;
    if (
      metavalOnly &&
      metavalResults.length > 0 &&
      !metavalResults.find((r) => r.taxon_id === t.taxon_id && r.classifier === profile.classifier)
    )
      return false;
    return true;
  });

  const ntcSum = (taxon_id: number) =>
    ntcForClassifier.reduce((sum, ntc) => sum + (ntc.abundanceMap[taxon_id] ?? 0), 0);

  const contaminantThreshold = contaminantConfig?.threshold ?? null;
  const eligibleRanks = contaminantConfig?.eligible_ranks
    ? new Set(contaminantConfig.eligible_ranks)
    : null;
  const isContaminant = (t: SampleProfileEntry) => {
    if (!hasNtc || contaminantThreshold == null || !eligibleRanks) return false;
    if (!eligibleRanks.has(t.rank ?? "no rank")) return false;
    return ntcSum(t.taxon_id) > contaminantThreshold;
  };

  const sorted = [...filtered].sort((a, b) => {
    if (taxSort.col === "name") return taxSort.dir * a.name.localeCompare(b.name);
    if (taxSort.col === "rank") return taxSort.dir * (a.rank ?? "").localeCompare(b.rank ?? "");
    if (taxSort.col === "superkingdom")
      return taxSort.dir * (a.superkingdom ?? "").localeCompare(b.superkingdom ?? "");
    if (taxSort.col === "ntc") return taxSort.dir * (ntcSum(a.taxon_id) - ntcSum(b.taxon_id));
    if (taxSort.col === "concordance") {
      const aCount = concordanceMap[a.taxon_id]?.size ?? 0;
      const bCount = concordanceMap[b.taxon_id]?.size ?? 0;
      if (aCount !== bCount) return taxSort.dir * (aCount - bCount);
      const aReads = (allProfiles ?? []).reduce((sum, p) => {
        const entry = p.profile?.find((e) => e.taxon_id === a.taxon_id);
        return sum + (entry?.abundance ?? 0);
      }, 0);
      const bReads = (allProfiles ?? []).reduce((sum, p) => {
        const entry = p.profile?.find((e) => e.taxon_id === b.taxon_id);
        return sum + (entry?.abundance ?? 0);
      }, 0);
      return taxSort.dir * (aReads - bReads);
    }
    return taxSort.dir * (a.abundance - b.abundance);
  });

  const totalPages = Math.ceil(sorted.length / TAX_PER_PAGE);
  const pageEntries = sorted.slice(taxPage * TAX_PER_PAGE, (taxPage + 1) * TAX_PER_PAGE);
  const maxAbundance =
    tableEntries.length > 0 ? Math.max(...tableEntries.map((t) => t.abundance)) : 1;

  function toggleSort(col: SortCol) {
    setTaxSort((prev) =>
      prev.col === col
        ? { col, dir: (prev.dir * -1) as 1 | -1 }
        : { col, dir: col === "name" || col === "superkingdom" ? 1 : -1 }
    );
    setTaxPage(0);
  }

  function sortArrow(col: SortCol) {
    if (taxSort.col !== col) return null;
    return taxSort.dir === 1 ? " ↑" : " ↓";
  }

  const kingdoms = ["Bacteria", "Viruses", "Eukaryota", "Archaea"];
  const kingdomCounts = Object.fromEntries(
    kingdoms.map((k) => [k, tableEntries.filter((t) => t.superkingdom === k).length])
  );

  interface ColDef {
    label: string;
    col: SortCol | null;
  }
  const columns: ColDef[] = [
    { label: "Organism", col: "name" },
    { label: "Rank", col: "rank" },
    { label: "Kingdom", col: "superkingdom" },
    { label: abundanceIsFraction ? "Abundance" : "Reads", col: "abundance" },
    ...(!abundanceIsFraction
      ? [
          {
            label: "Classifiers",
            col: allClassifierNames.length > 1 ? "concordance" : null,
          } as ColDef,
        ]
      : []),
    ...(showNtcColumn
      ? [
          {
            label: abundanceIsFraction ? "Abundance in NTC" : "Reads in NTC",
            col: hasNtc ? "ntc" : null,
          } as ColDef,
        ]
      : []),
    { label: "% of non-host", col: null },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="flex-1" />
        {kingdoms.map((k) => kingdomCounts[k] > 0 && <KingdomBadge key={k} kingdom={k} />)}
      </div>
      <div className="grid grid-cols-4 gap-2">
        <div className="bg-gray-50 rounded-lg px-3 py-2">
          <p className="text-xs text-gray-400 mb-0.5">Total classified</p>
          <p className="text-sm font-medium text-gray-700">{fmt(totalReads - unclassReads)}</p>
        </div>
        <div className="bg-gray-50 rounded-lg px-3 py-2">
          <p className="text-xs text-gray-400 mb-0.5">Non-host reads</p>
          <p className="text-sm font-medium text-gray-700">{fmt(nonHostTotal)}</p>
        </div>
        <div className="bg-gray-50 rounded-lg px-3 py-2">
          <p className="text-xs text-gray-400 mb-0.5">Organisms shown</p>
          <p className="text-sm font-medium text-gray-700">{fmt(filtered.length)}</p>
        </div>
        <div className="bg-gray-50 rounded-lg px-3 py-2">
          <p className="text-xs text-gray-400 mb-0.5">Page</p>
          <p className="text-sm font-medium text-gray-700">
            {taxPage + 1} / {Math.max(1, totalPages)}
          </p>
        </div>
      </div>

      <div className="flex gap-2 items-center">
        <input
          type="text"
          placeholder="Search organism…"
          value={taxSearch}
          onChange={(e) => {
            setTaxSearch(e.target.value);
            saveFilters({ taxSearch: e.target.value });
            setTaxPage(0);
          }}
          className="flex-1 text-xs border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-blue-300"
        />
        <div className="relative">
          <button
            onClick={() => setKingdomOpen((o) => !o)}
            className={`text-xs border rounded-lg px-3 py-1.5 bg-white flex items-center gap-1.5 transition-colors ${
              taxKingdoms.length > 0
                ? "border-blue-300 text-blue-600"
                : "border-gray-200 text-gray-500"
            }`}
          >
            {taxKingdoms.length > 0 ? `Kingdom (${taxKingdoms.length})` : "All kingdoms"}
            <svg
              className={`w-3 h-3 transition-transform ${kingdomOpen ? "rotate-180" : ""}`}
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
          {kingdomOpen && (
            <div className="absolute left-0 top-full mt-1 bg-white border border-gray-100 rounded-xl shadow-lg z-20 min-w-36 py-1">
              {kingdoms.map((k) => (
                <label
                  key={k}
                  className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={taxKingdoms.includes(k)}
                    onChange={(e) => {
                      setTaxKingdoms((prev) => {
                        const next = e.target.checked ? [...prev, k] : prev.filter((x) => x !== k);
                        setSessionKingdoms(next);
                        saveFilters({ kingdoms: next });
                        return next;
                      });
                      setTaxPage(0);
                    }}
                    className="rounded"
                  />
                  <span className="text-xs text-gray-600">{k}</span>
                </label>
              ))}
              {taxKingdoms.length > 0 && (
                <button
                  onClick={() => {
                    setTaxKingdoms([]);
                    setSessionKingdoms([]);
                    saveFilters({ kingdoms: [] });
                    setTaxPage(0);
                  }}
                  className="w-full text-left px-3 py-1.5 text-xs text-gray-400 hover:text-gray-600 border-t border-gray-50 mt-1"
                >
                  Clear
                </button>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1.5 border border-gray-200 rounded-lg px-3 py-1.5 bg-white">
          <span className="text-xs text-gray-400 whitespace-nowrap">Min reads</span>
          <input
            type="number"
            min="1"
            value={concordanceMin}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!isNaN(v) && v >= 1) {
                setConcordanceMin(v);
                saveFilters({ concordanceMin: v });
              }
            }}
            className="w-12 text-xs text-gray-700 outline-none text-center bg-transparent"
          />
        </div>
        {metavalResults.length > 0 && (
          <button
            onClick={() => {
              setMetavalOnly((o) => {
                saveFilters({ metavalOnly: !o });
                return !o;
              });
              setTaxPage(0);
            }}
            className={`text-xs border rounded-lg px-3 py-1.5 transition-colors ${
              metavalOnly
                ? "border-blue-300 bg-blue-50 text-blue-600"
                : "border-gray-200 bg-white text-gray-500 hover:bg-gray-50"
            }`}
          >
            Metaval only
          </button>
        )}
      </div>

      {pageEntries.length === 0 ? (
        <p className="text-xs text-gray-400 py-4 text-center">No organisms match your filters.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr>
                {columns.map(({ label, col }) => (
                  <th
                    key={label}
                    onClick={col ? () => toggleSort(col) : undefined}
                    className={`pb-2 text-xs font-medium text-gray-400 border-b border-gray-100 ${
                      col ? "cursor-pointer hover:text-gray-600 select-none" : ""
                    }`}
                  >
                    {label}
                    {col ? sortArrow(col) : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageEntries.map((t, i) => {
                const pct = nonHostTotal > 0 ? (t.abundance / nonHostTotal) * 100 : 0;
                const pctStr = pct < 0.001 ? "<0.001%" : `${pct.toFixed(3)}%`;
                const mv = metavalResults.find(
                  (r) => r.taxon_id === t.taxon_id && r.classifier === profile.classifier
                );
                return (
                  <tr key={i} className="border-t border-gray-50 hover:bg-gray-50">
                    <td className="py-2 pr-3 text-xs text-gray-700">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <Link
                          to={`/taxa/${t.taxon_id}`}
                          className="italic truncate hover:text-blue-600 hover:underline transition-colors"
                        >
                          {t.name}
                        </Link>
                        {mv && (
                          <Link
                            to={`/samples/${sampleId}/metaval/${mv._id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded-full text-xs bg-green-50 text-green-700 hover:bg-green-100 transition-colors"
                          >
                            <span className="underline">metaval</span>
                          </Link>
                        )}
                        {pathogenIds?.has(t.taxon_id) && (
                          <span className="flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded-full text-xs bg-red-50 text-red-600 font-medium">
                            pathogen
                          </span>
                        )}
                        {isContaminant(t) && (
                          <span
                            title={`NTC reads (${ntcSum(
                              t.taxon_id
                            )}) exceed threshold of ${contaminantThreshold}`}
                            className="flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded-full text-xs bg-orange-50 text-orange-700 font-medium"
                          >
                            contaminant
                          </span>
                        )}
                        {outbreakTaxonIds.has(t.taxon_id) && (
                          <Link
                            to={`/alerts#taxon-${t.taxon_id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="flex-shrink-0 inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-xs bg-amber-50 text-amber-600 hover:bg-amber-100 transition-colors"
                          >
                            <svg className="w-2.5 h-2.5" viewBox="0 0 16 16" fill="none">
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
                            <span>alert</span>
                          </Link>
                        )}
                      </div>
                    </td>
                    <td className="py-2 pr-3 text-xs text-gray-400">{t.rank ?? "—"}</td>
                    <td className="py-2 pr-3">
                      <KingdomBadge kingdom={t.superkingdom} />
                    </td>
                    <td className="py-2 pr-3 text-xs text-gray-500 tabular-nums">
                      {abundanceIsFraction ? fmtPct(t.abundance * 100) : fmt(t.abundance)}
                    </td>
                    {!abundanceIsFraction && (
                      <td className="py-2 pr-3">
                        {allClassifierNames.length > 1 ? (
                          (() => {
                            const readsPerClassifier = allClassifierNames.map((c) => {
                              const p = (allProfiles ?? []).find((p) => p.classifier === c);
                              const entry = p?.profile?.find((e) => e.taxon_id === t.taxon_id);
                              return { classifier: c, reads: entry?.abundance ?? 0 };
                            });
                            return (
                              <div
                                className="flex items-center gap-1"
                                title={readsPerClassifier
                                  .map((r) => `${r.classifier}: ${r.reads.toLocaleString()} reads`)
                                  .join("\n")}
                              >
                                {readsPerClassifier.map(({ classifier: c, reads }) => (
                                  <span
                                    key={c}
                                    className={`w-2 h-2 rounded-full flex-shrink-0 ${
                                      reads >= concordanceMin ? "bg-blue-500" : "bg-gray-200"
                                    }`}
                                  />
                                ))}
                                <span className="text-xs text-gray-400 ml-0.5">
                                  {readsPerClassifier
                                    .map((r) => r.reads.toLocaleString())
                                    .join(" / ")}
                                </span>
                              </div>
                            );
                          })()
                        ) : (
                          <span className="text-gray-300 text-xs">—</span>
                        )}
                      </td>
                    )}
                    {showNtcColumn && (
                      <td className="py-2 pr-3 text-xs tabular-nums">
                        {!hasNtc ? (
                          <span className="text-gray-300">N/A</span>
                        ) : (
                          (() => {
                            const vals = ntcForClassifier.map((ntc) => ({
                              sample_id: ntc.sample_id,
                              count: ntc.abundanceMap[t.taxon_id] ?? 0,
                            }));
                            const allZero = vals.every((v) => v.count === 0);
                            const fmtVal = (v: number) =>
                              abundanceIsFraction ? fmtPct(v * 100) : v.toLocaleString();
                            return (
                              <span
                                className={allZero ? "text-gray-300" : "text-amber-600 font-medium"}
                                title={vals
                                  .map((v) => `${v.sample_id}: ${fmtVal(v.count)}`)
                                  .join("\n")}
                              >
                                {vals.map((v) => fmtVal(v.count)).join(", ")}
                              </span>
                            );
                          })()
                        )}
                      </td>
                    )}
                    <td className="py-2">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 bg-gray-100 rounded-full h-1.5 min-w-0">
                          <div
                            className="bg-blue-400 h-1.5 rounded-full"
                            style={{
                              width: `${Math.min(100, (t.abundance / maxAbundance) * 100).toFixed(
                                1
                              )}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs text-gray-400 tabular-nums flex-shrink-0 w-16 text-right">
                          {pctStr}
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {totalPages > 1 && (
        <div className="flex items-center gap-2 mt-3 text-xs text-gray-400">
          <button
            onClick={() => setTaxPage((p) => Math.max(0, p - 1))}
            disabled={taxPage === 0}
            className="px-2 py-1 border border-gray-200 rounded disabled:opacity-40 hover:bg-gray-50"
          >
            ← Prev
          </button>
          <span>
            {taxPage * TAX_PER_PAGE + 1}–{Math.min((taxPage + 1) * TAX_PER_PAGE, sorted.length)} of{" "}
            {sorted.length}
          </span>
          <button
            onClick={() => setTaxPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={taxPage >= totalPages - 1}
            className="px-2 py-1 border border-gray-200 rounded disabled:opacity-40 hover:bg-gray-50"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
