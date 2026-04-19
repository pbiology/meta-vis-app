import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate, Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getSample, getProfile, getNtcProfiles } from "../api/samples";
import Badge from "../components/Badge";
import { MetricStrip } from "../components/MetricStrip";
import TaxonomyTable from "../components/TaxonomyTable";
import { getMetavalForSample } from "../api/metaval";
import { getOutbreaks, getPathogens } from "../api/alerts";
import { fmt, fmtPct } from "../utils/format";

function DataWarning({ message }) {
  return <p className="text-xs text-amber-600 bg-amber-50 rounded px-3 py-1.5 mb-2">{message}</p>;
}

export default function SampleDetail() {
  const { sampleId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(null);

  // Primary data — must succeed for the page to render
  const {
    data: sample,
    isLoading: sampleLoading,
    isError: sampleError,
  } = useQuery({
    queryKey: ["sample", sampleId],
    queryFn: () => getSample(sampleId),
  });

  const {
    data: profile,
    isLoading: profileLoading,
    isError: profileError,
  } = useQuery({
    queryKey: ["profile", sampleId],
    queryFn: () => getProfile(sampleId),
  });

  // Secondary data — can fail independently, show inline warnings
  const { data: metavalResults = [], isError: metavalError } = useQuery({
    queryKey: ["metaval", sampleId],
    queryFn: () => getMetavalForSample(sampleId),
    enabled: !!sample,
  });

  const { data: ntcProfiles = [], isError: ntcError } = useQuery({
    queryKey: ["ntcProfiles", sampleId],
    queryFn: () => getNtcProfiles(sampleId),
    enabled: !!sample,
  });

  const { data: outbreakData, isError: outbreakError } = useQuery({
    queryKey: ["outbreaks", { windowDays: 14 }],
    queryFn: () => getOutbreaks(14),
  });

  const { data: pathogenList = [], isError: pathogenError } = useQuery({
    queryKey: ["pathogens"],
    queryFn: () => getPathogens(),
  });

  // Derived state
  const outbreakTaxonIds = useMemo(
    () => new Set(outbreakData?.outbreaks?.map((o) => o.taxon_id) ?? []),
    [outbreakData]
  );

  const pathogenIds = useMemo(() => new Set(pathogenList.map((p) => p.taxon_id)), [pathogenList]);

  const pathogenMap = useMemo(
    () => Object.fromEntries(pathogenList.map((p) => [p.taxon_id, p])),
    [pathogenList]
  );

  // Set active classifier tab when profile loads
  useEffect(() => {
    if (profile?.profiles?.length && activeTab === null) {
      const requestedClassifier = searchParams.get("classifier");
      const match = profile.profiles.find((p) => p.classifier === requestedClassifier);
      setActiveTab(match ? requestedClassifier : profile.profiles[0].classifier);
    }
  }, [profile, activeTab, searchParams]);

  if (sampleLoading || profileLoading)
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">
        Loading&hellip;
      </div>
    );
  if (sampleError || profileError)
    return (
      <div className="flex items-center justify-center h-full text-sm text-red-500">
        Failed to load sample.
      </div>
    );

  const isTrana = Boolean(sample?.trana);
  const qc = sample?.taxprofiler;
  const fp = qc?.fastp;
  const bt = qc?.bowtie2;
  const trana = sample?.trana;
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
          {isTrana ? (
            <MetricStrip
              metrics={[
                { label: "Total reads",      value: fmt(trana?.nanoplot_unprocessed?.number_of_reads), sub: "before processing" },
                { label: "Passed filter",    value: fmt(trana?.nanoplot_processed?.number_of_reads),   sub: "after processing" },
                { label: "Mean read length",
                  value: trana?.nanoplot_processed?.mean_read_length != null
                    ? trana.nanoplot_processed.mean_read_length.toFixed(0) : "—",
                  sub: "bp" },
                { label: "Mean quality",
                  value: trana?.nanoplot_processed?.mean_read_quality != null
                    ? trana.nanoplot_processed.mean_read_quality.toFixed(1) : "—",
                  sub: "Q" },
                { label: "Read N50", value: fmt(trana?.nanoplot_processed?.read_length_n50), sub: "bp" },
              ]}
            />
          ) : (
            <MetricStrip
              metrics={[
                { label: "Total reads",   value: fp ? fmt(fp.total_reads_before_filtering) : "—", sub: "before filtering" },
                { label: "Passed filter", value: fp ? fmt(fp.passed_filter_reads) : "—",
                  sub: fp ? `${fmtPct((fp.passed_filter_reads / fp.total_reads_before_filtering) * 100)} of raw` : "" },
                { label: "Host removed",  value: bt ? fmtPct(bt.overall_alignment_rate) : "—", sub: "bowtie2" },
                { label: "Q20 rate",      value: fmtPct(fp?.q20_rate ? fp.q20_rate * 100 : null), sub: "fastp" },
                { label: "Q30 rate",      value: fmtPct(fp?.q30_rate ? fp.q30_rate * 100 : null), sub: "fastp" },
              ]}
            />
          )}
        </section>

        {/* Classifier metrics */}
        {!isTrana && classifiers.length > 0 && (
          <section>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
              Classifier metrics
            </p>
            <div className="flex flex-col gap-2">
              {classifiers.map((clf) => {
                const clfQc = qc?.classifiers?.[clf.classifier];
                return (
                  <div key={clf.classifier}>
                    <p className="text-xs text-gray-400 mb-1.5">
                      {clf.classifier}
                      <span className="ml-1.5 text-gray-300">&middot; {clf.classifier_db}</span>
                    </p>
                    <MetricStrip
                      metrics={[
                        {
                          label: "Unclassified",
                          value: fmtPct(clfQc?.pct_unclassified),
                          sub: clfQc ? `${fmt(clfQc.unclassified_reads)} reads` : "",
                          warn: (clfQc?.pct_unclassified ?? 0) > 20,
                        },
                        { label: "Species", value: fmt(clfQc?.num_species), sub: clf.classifier },
                        { label: "Genera",  value: fmt(clfQc?.num_genera),  sub: clf.classifier },
                      ]}
                    />
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Metaval — viral taxa per classifier (taxprofiler only) */}
        {!isTrana && metavalError && (
          <DataWarning message="Failed to load metaval data — metaval results may be missing." />
        )}
        {!isTrana && (
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
                              {r.taxon_name.replace(/^taxid_\d+_/, "").replace(/-/g, " ")}
                            </Link>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {/* Known pathogens — detected taxa that are on the pathogens list */}
        {(() => {
          if (pathogenError) {
            return (
              <DataWarning message="Failed to load pathogen data — known pathogen detection unavailable." />
            );
          }
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
                        {pathogenMap[t.taxon_id]?.notes ?? (
                          <span className="text-gray-300">{"—"}</span>
                        )}
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
                              <span className="text-gray-300">{"—"}</span>
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
        {(outbreakError || ntcError) && (
          <DataWarning
            message={
              outbreakError && ntcError
                ? "Failed to load outbreak and NTC data — outbreak badges and NTC columns may be missing."
                : outbreakError
                  ? "Failed to load outbreak data — outbreak badges may be missing."
                  : "Failed to load NTC data — NTC columns may be missing."
            }
          />
        )}
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
                    abundanceIsFraction={isTrana}
                    isNtc={sample?.sample_type !== "sample"}
                  />
                ) : null
              )}
          </section>
        )}
      </div>
    </div>
  );
}
