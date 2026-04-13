import { useState, useEffect } from "react";
import { useParams, useNavigate, Link, useSearchParams } from "react-router-dom";
import { getSample, getProfile, getNtcProfiles } from "../api/samples";
import Badge from "../components/Badge";
import MetricCard from "../components/MetricCard";
import { getMetavalForSample } from "../api/metaval";
import { getOutbreaks, getPathogens } from "../api/alerts";
import { useAuth } from "../context/AuthContext";

function fmt(n, decimals = 0) {
  if (n === undefined || n === null) return "—";
  return typeof n === "number"
    ? n.toLocaleString(undefined, { maximumFractionDigits: decimals })
    : n;
}

function fmtPct(n) {
  if (n === undefined || n === null) return "—";
  return `${n.toFixed(1)}%`;
}

const KINGDOM_BADGE = {
  Bacteria: { bg: "bg-blue-50", text: "text-blue-700" },
  Viruses: { bg: "bg-red-50", text: "text-red-700" },
  Eukaryota: { bg: "bg-amber-50", text: "text-amber-700" },
  Archaea: { bg: "bg-purple-50", text: "text-purple-700" },
};

function KingdomBadge({ kingdom }) {
  const style = KINGDOM_BADGE[kingdom];
  if (!style)
    return (
      <span className="inline-block text-xs px-1.5 py-0.5 rounded bg-gray-50 text-gray-400">
        {kingdom ?? "Unknown"}
      </span>
    );
  return (
    <span className={`inline-block text-xs px-1.5 py-0.5 rounded ${style.bg} ${style.text}`}>
      {kingdom}
    </span>
  );
}

const HOST_IDS = new Set([9606, 1, 0, 131567]);

function TaxonomyTable({
  profile,
  allProfiles,
  clfQc,
  metavalResults,
  sampleId,
  outbreakTaxonIds,
  ntcProfiles,
  pathogenIds,
}) {
  const { preferences } = useAuth();
  const [taxSearch, setTaxSearch] = useState("");
  const [taxKingdoms, setTaxKingdoms] = useState(
    () => preferences?.preferred_kingdoms ?? ["Viruses"],
  );
  const [taxSort, setTaxSort] = useState({ col: "abundance", dir: -1 });
  const [taxPage, setTaxPage] = useState(0);
  const [metavalOnly, setMetavalOnly] = useState(false);
  const [kingdomOpen, setKingdomOpen] = useState(false);
  const [concordanceMin, setConcordanceMin] = useState(1);
  const TAX_PER_PAGE = 50;

  // Build a map of taxon_id -> Set of classifier names that detected it
  // at or above the concordanceMin threshold, across all classifiers for this sample.
  const allClassifierNames = (allProfiles ?? []).map((p) => p.classifier);
  const concordanceMap = {};
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
              !HOST_IDS.has(t.taxon_id) &&
              t.name !== "unclassified" &&
              !t.name?.startsWith("unclassified ")
          )
          .reduce((sum, t) => sum + t.abundance, 0);

  // NTC profiles for this classifier — list of {sample_id, abundanceMap}
  const ntcForClassifier = ntcProfiles.map((ntc) => ({
    sample_id: ntc.sample_id,
    abundanceMap: ntc.classifiers?.[profile.classifier] ?? {},
  }));
  const hasNtc = ntcForClassifier.length > 0;

  const tableEntries = allEntries.filter(
    (t) =>
      !HOST_IDS.has(t.taxon_id) && t.name !== "unclassified" && !t.name?.startsWith("unclassified ")
  );

  const filtered = tableEntries.filter((t) => {
    if (taxSearch && !t.name?.toLowerCase().includes(taxSearch.toLowerCase())) return false;
    if (taxKingdoms.length > 0 && !taxKingdoms.includes(t.superkingdom)) return false;
    if (
      metavalOnly &&
      !metavalResults.find((r) => r.taxon_id === t.taxon_id && r.classifier === profile.classifier)
    )
      return false;
    return true;
  });

  const ntcSum = (taxon_id) =>
    ntcForClassifier.reduce((sum, ntc) => sum + (ntc.abundanceMap[taxon_id] ?? 0), 0);

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
      // Secondary sort: total reads across all classifiers
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

  function toggleSort(col) {
    setTaxSort((prev) =>
      prev.col === col
        ? { col, dir: prev.dir * -1 }
        : { col, dir: col === "name" || col === "superkingdom" ? 1 : -1 }
    );
    setTaxPage(0);
  }

  function sortArrow(col) {
    if (taxSort.col !== col) return null;
    return taxSort.dir === 1 ? " ↑" : " ↓";
  }

  const kingdoms = ["Bacteria", "Viruses", "Eukaryota", "Archaea"];
  const kingdomCounts = Object.fromEntries(
    kingdoms.map((k) => [k, tableEntries.filter((t) => t.superkingdom === k).length])
  );

  return (
    <div className="flex flex-col gap-3">
      {/* Kingdom badges + stats */}
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

      {/* Filters */}
      <div className="flex gap-2 items-center">
        <input
          type="text"
          placeholder="Search organism…"
          value={taxSearch}
          onChange={(e) => {
            setTaxSearch(e.target.value);
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
                      setTaxKingdoms((prev) =>
                        e.target.checked ? [...prev, k] : prev.filter((x) => x !== k)
                      );
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
              if (!isNaN(v) && v >= 1) setConcordanceMin(v);
            }}
            className="w-12 text-xs text-gray-700 outline-none text-center bg-transparent"
          />
        </div>
        {metavalResults.length > 0 && (
          <button
            onClick={() => {
              setMetavalOnly((o) => !o);
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

      {/* Table */}
      {pageEntries.length === 0 ? (
        <p className="text-xs text-gray-400 py-4 text-center">No organisms match your filters.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left" style={{ tableLayout: "fixed" }}>
            <colgroup>
              <col style={{ width: "30%" }} />
              <col style={{ width: "9%" }} />
              <col style={{ width: "9%" }} />
              <col style={{ width: "9%" }} />
              <col style={{ width: "11%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "20%" }} />
            </colgroup>
            <thead>
              <tr>
                {[
                  { label: "Organism", col: "name" },
                  { label: "Rank", col: "rank" },
                  { label: "Kingdom", col: "superkingdom" },
                  { label: "Reads", col: "abundance" },
                  {
                    label: "Classifiers",
                    col: allClassifierNames.length > 1 ? "concordance" : null,
                  },
                  { label: "Reads in NTC", col: hasNtc ? "ntc" : null },
                  { label: "% of non-host", col: null },
                ].map(({ label, col }) => (
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
                      {fmt(t.abundance)}
                    </td>
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
                          return (
                            <span
                              className={allZero ? "text-gray-300" : "text-amber-600 font-medium"}
                              title={vals
                                .map((v) => `${v.sample_id}: ${v.count.toLocaleString()}`)
                                .join("\n")}
                            >
                              {vals.map((v) => v.count.toLocaleString()).join(", ")}
                            </span>
                          );
                        })()
                      )}
                    </td>
                    <td className="py-2">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 bg-gray-100 rounded-full h-1.5 min-w-0">
                          <div
                            className="bg-blue-400 h-1.5 rounded-full"
                            style={{
                              width: `${Math.min(100, (t.abundance / maxAbundance) * 100).toFixed(1)}%`,
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

export default function SampleDetail() {
  const { sampleId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [sample, setSample] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState(null);
  const [metavalResults, setMetavalResults] = useState([]);
  const [outbreakTaxonIds, setOutbreakTaxonIds] = useState(new Set());
  const [ntcProfiles, setNtcProfiles] = useState([]);
  const [pathogenIds, setPathogenIds] = useState(new Set());
  const [pathogenMap, setPathogenMap] = useState({});

  useEffect(() => {
    async function load() {
      try {
        const [s, p] = await Promise.all([getSample(sampleId), getProfile(sampleId)]);
        setSample(s);
        setProfile(p);
        getMetavalForSample(sampleId)
          .then(setMetavalResults)
          .catch(() => {});
        getNtcProfiles(sampleId)
          .then(setNtcProfiles)
          .catch(() => {});
        getOutbreaks(14)
          .then((data) => {
            const ids = new Set(data.outbreaks.map((o) => o.taxon_id));
            setOutbreakTaxonIds(ids);
          })
          .catch(() => {});
        getPathogens()
          .then((list) => {
            setPathogenIds(new Set(list.map((p) => p.taxon_id)));
            setPathogenMap(Object.fromEntries(list.map((p) => [p.taxon_id, p])));
          })
          .catch(() => {});
        if (p.profiles?.length) {
          const requestedClassifier = searchParams.get("classifier");
          const match = p.profiles.find((p) => p.classifier === requestedClassifier);
          setActiveTab(match ? requestedClassifier : p.profiles[0].classifier);
        }
      } catch {
        setError("Failed to load sample.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [sampleId]);

  if (loading)
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">Loading…</div>
    );
  if (error)
    return (
      <div className="flex items-center justify-center h-full text-sm text-red-500">{error}</div>
    );

  const qc = sample?.taxprofiler;
  const fp = qc?.fastp;
  const bt = qc?.bowtie2;
  const classifiers = profile?.profiles ?? [];

  return (
    <div className="flex flex-col h-full">
      {/* Topbar */}
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <button
          onClick={() => navigate(-1)}
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
          Back
        </button>
        <span className="text-gray-200">/</span>
        <h1 className="text-sm font-medium text-gray-900 flex-1 font-mono">
          {sample?.sample_id ?? sampleId}
        </h1>
        <Badge type={sample?.sample_type} />
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-6">
        {/* QC metrics — classifier-agnostic */}
        <section>
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
            QC metrics
          </p>
          <div className="grid grid-cols-4 gap-2.5">
            <MetricCard
              label="Total reads"
              value={fp ? fmt(fp.total_reads_before_filtering) : "—"}
              sub="before filtering"
            />
            <MetricCard
              label="Passed filter"
              value={fp ? fmt(fp.passed_filter_reads) : "—"}
              sub={
                fp
                  ? `${fmtPct((fp.passed_filter_reads / fp.total_reads_before_filtering) * 100)} of raw`
                  : ""
              }
            />
            <MetricCard
              label="Host removed"
              value={bt ? fmtPct(bt.overall_alignment_rate) : "—"}
              sub="bowtie2 alignment"
            />
            <MetricCard
              label="Q20 rate"
              value={fmtPct(fp?.q20_rate ? fp.q20_rate * 100 : null)}
              sub="fastp"
            />
            <MetricCard
              label="Q30 rate"
              value={fmtPct(fp?.q30_rate ? fp.q30_rate * 100 : null)}
              sub="fastp"
            />
          </div>
        </section>

        {/* Classifier-specific QC metrics */}
        {classifiers.length > 0 && (
          <section>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
              Classifier metrics
            </p>
            <div className="flex flex-col gap-4">
              {classifiers.map((clf) => {
                const clfQc = qc?.classifiers?.[clf.classifier];
                return (
                  <div key={clf.classifier}>
                    <p className="text-xs text-gray-400 mb-2">
                      {clf.classifier}
                      <span className="ml-1.5 text-gray-300">· {clf.classifier_db}</span>
                    </p>
                    <div className="grid grid-cols-4 gap-2.5">
                      <MetricCard
                        label="Unclassified"
                        value={fmtPct(clfQc?.pct_unclassified)}
                        sub={clfQc ? `${fmt(clfQc.unclassified_reads)} reads` : ""}
                        warn={(clfQc?.pct_unclassified ?? 0) > 20}
                      />
                      <MetricCard
                        label="Species"
                        value={fmt(clfQc?.num_species)}
                        sub={clf.classifier}
                      />
                      <MetricCard
                        label="Genera"
                        value={fmt(clfQc?.num_genera)}
                        sub={clf.classifier}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Metaval — viral taxa per classifier */}
        <section className="bg-white border border-gray-100 rounded-xl">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">
              Metaval
            </p>
            {metavalResults.length > 0 && (
              <div className="flex gap-1.5">
                {classifiers.map((clf) => {
                  const hasResults = metavalResults.some((r) => r.classifier === clf.classifier);
                  if (!hasResults) return null;
                  return (
                    <button
                      key={clf.classifier}
                      onClick={() => setActiveTab(clf.classifier)}
                      className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                        activeTab === clf.classifier
                          ? "bg-gray-900 text-white font-medium"
                          : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                      }`}
                    >
                      {clf.classifier}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          {metavalResults.length === 0 ? (
            <p className="px-4 py-6 text-xs text-gray-300 text-center">No viral taxon found</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr>
                    <th className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100">
                      Viral taxon
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {metavalResults
                    .filter((r) => r.classifier === activeTab)
                    .map((r) => (
                      <tr key={r._id} className="border-t border-gray-50 hover:bg-gray-50">
                        <td className="px-4 py-2.5">
                          <Link
                            to={`/samples/${sampleId}/metaval/${r._id}`}
                            className="text-xs italic text-gray-700 hover:text-blue-600 underline transition-colors"
                          >
                            {r.taxon_name.replace(/-/g, " ")}
                          </Link>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Known pathogens — detected taxa that are on the pathogens list */}
        {(() => {
          if (pathogenIds.size === 0 || classifiers.length === 0) return null;
          // Collect all detected pathogen taxa across all classifiers
          const detected = [];
          const seen = new Set();
          for (const clf of classifiers) {
            for (const entry of clf.profile ?? []) {
              if (pathogenIds.has(entry.taxon_id) && !seen.has(entry.taxon_id)) {
                seen.add(entry.taxon_id);
                detected.push(entry);
              }
            }
          }
          if (detected.length === 0) return null;
          return (
            <section className="bg-white border border-red-200 rounded-xl">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-red-100">
                <svg
                  className="w-3.5 h-3.5 text-red-500 flex-shrink-0"
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
                <p className="text-xs font-medium text-red-600 uppercase tracking-wider flex-1">
                  Known pathogens detected
                </p>
                <span className="text-xs text-red-400">
                  {detected.length} taxon{detected.length !== 1 ? "a" : ""}
                </span>
              </div>
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr>
                    <th className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100">
                      Taxon
                    </th>
                    <th className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100">
                      Kingdom
                    </th>
                    <th className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100">
                      Notes
                    </th>
                    {classifiers.map((clf) => (
                      <th
                        key={clf.classifier}
                        className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100 whitespace-nowrap"
                      >
                        {clf.classifier}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {detected.map((t) => (
                    <tr key={t.taxon_id} className="border-b border-gray-50">
                      <td className="px-4 py-3 text-xs italic text-gray-800 font-medium">
                        {t.name}
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">{t.superkingdom ?? "—"}</td>
                      <td className="px-4 py-3 text-xs text-gray-400">
                        {pathogenMap[t.taxon_id]?.notes ?? <span className="text-gray-300">—</span>}
                      </td>
                      {classifiers.map((clf) => {
                        const entry = clf.profile?.find((e) => e.taxon_id === t.taxon_id);
                        return (
                          <td key={clf.classifier} className="px-4 py-3 text-xs tabular-nums">
                            {entry ? (
                              <span className="text-red-600 font-medium">
                                {entry.abundance.toLocaleString()}
                              </span>
                            ) : (
                              <span className="text-gray-300">—</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          );
        })()}

        {/* Taxonomy — tabs per classifier */}

        {/* Taxonomy — tabs per classifier */}
        {classifiers.length > 0 && (
          <section className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">
                Taxonomy
              </p>
              <div className="flex gap-1.5">
                {classifiers.map((clf) => (
                  <button
                    key={clf.classifier}
                    onClick={() => setActiveTab(clf.classifier)}
                    className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                      activeTab === clf.classifier
                        ? "bg-gray-900 text-white font-medium"
                        : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                    }`}
                  >
                    {clf.classifier}
                  </button>
                ))}
              </div>
            </div>
            {activeTab &&
              classifiers.map((clf) =>
                clf.classifier === activeTab ? (
                  <TaxonomyTable
                    key={clf.classifier}
                    profile={clf}
                    allProfiles={classifiers}
                    clfQc={qc?.classifiers?.[clf.classifier]}
                    metavalResults={metavalResults}
                    sampleId={sampleId}
                    outbreakTaxonIds={outbreakTaxonIds}
                    ntcProfiles={ntcProfiles}
                    pathogenIds={pathogenIds}
                  />
                ) : null
              )}
          </section>
        )}
      </div>
    </div>
  );
}
