import { useState, useEffect, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getSample, getProfile, getNtcProfiles } from "../api/samples";
import Badge, { type BadgeType } from "./Badge";
import { MetricStrip } from "./MetricStrip";
import TaxonomyTable from "./TaxonomyTable";
import { useReportBuilder } from "../context/ReportBuilderContext";
import { getMetavalForSample } from "../api/metaval";
import { getOutbreaks, getPathogens } from "../api/alerts";
import { fmt, fmtPct } from "../utils/format";
import { TAXON_ID_HUMAN } from "../utils/taxonomy";
import type { PathogenItem, SampleProfile, SampleProfileEntry } from "../api/types";

interface DataWarningProps {
  message: string;
}

function DataWarning({ message }: Readonly<DataWarningProps>) {
  return <p className="text-xs text-amber-600 bg-amber-50 rounded px-3 py-1.5 mb-2">{message}</p>;
}

interface NanoplotStats {
  number_of_reads?: number;
  mean_read_length?: number;
  mean_read_quality?: number;
  read_length_n50?: number;
}

interface TranaQc {
  nanoplot_unprocessed?: NanoplotStats;
  nanoplot_processed?: NanoplotStats;
}

interface FastpStats {
  total_reads_before_filtering?: number;
  passed_filter_reads?: number;
  q20_rate?: number;
  q30_rate?: number;
}

interface Bowtie2Stats {
  overall_alignment_rate?: number;
  aligned_none?: number;
}

interface ClassifierQcStats {
  unclassified_reads?: number;
  total_reads?: number;
  queries_aligned?: number;
  [key: string]: unknown;
}

interface TaxprofilerQc {
  fastp?: FastpStats;
  bowtie2?: Bowtie2Stats;
  classifiers?: Record<string, ClassifierQcStats | undefined>;
}

type SuperkingdomKey = "Bacteria" | "Eukaryota" | "Viruses" | "Archaea";

interface ClassifierMetricsRowProps {
  clf: SampleProfile;
  clfQc: ClassifierQcStats | undefined;
}

function ClassifierMetricsRow({ clf, clfQc }: Readonly<ClassifierMetricsRowProps>) {
  const sumBySuperkingdom: Record<SuperkingdomKey, number> = {
    Bacteria: 0,
    Eukaryota: 0,
    Viruses: 0,
    Archaea: 0,
  };
  let humanReads = 0;
  for (const e of clf.profile ?? []) {
    if (e.taxon_id === TAXON_ID_HUMAN) humanReads += e.abundance ?? 0;
    const sk = e.superkingdom as SuperkingdomKey | null | undefined;
    if (sk && sk in sumBySuperkingdom) {
      sumBySuperkingdom[sk] += e.abundance ?? 0;
    }
  }
  const eukReads = Math.max(0, sumBySuperkingdom.Eukaryota - humanReads);
  const bacReads = sumBySuperkingdom.Bacteria;
  const virReads = sumBySuperkingdom.Viruses;
  const archReads = sumBySuperkingdom.Archaea;
  const unclassReads = clfQc?.unclassified_reads ?? 0;
  const accountedReads = humanReads + eukReads + bacReads + archReads + virReads + unclassReads;
  const totalReads = clfQc?.total_reads ?? clfQc?.queries_aligned ?? accountedReads;
  let totalSub: string | null = null;
  if (clfQc?.total_reads != null) {
    totalSub = `of ${fmt(clfQc.total_reads)} reads`;
  } else if (clfQc?.queries_aligned != null) {
    totalSub = `of ${fmt(clfQc.queries_aligned)} aligned queries`;
  }
  const otherReads = Math.max(0, totalReads - accountedReads);
  const pct = (n: number) => (totalReads > 0 ? (n / totalReads) * 100 : 0);
  return (
    <div>
      <p className="text-xs text-gray-400 mb-1.5">
        {clf.classifier}
        <span className="ml-1.5 text-gray-300">&middot; {clf.classifier_db}</span>
        {totalSub && <span className="ml-1.5 text-gray-300">&middot; {totalSub}</span>}
      </p>
      <MetricStrip
        metrics={[
          {
            label: "Unclassified",
            value: fmtPct(pct(unclassReads), 2),
            sub: `${fmt(unclassReads)} reads`,
            warn: pct(unclassReads) > 20,
          },
          { label: "Human", value: fmtPct(pct(humanReads), 2), sub: `${fmt(humanReads)} reads` },
          { label: "Viruses", value: fmtPct(pct(virReads), 2), sub: `${fmt(virReads)} reads` },
          { label: "Bacteria", value: fmtPct(pct(bacReads), 2), sub: `${fmt(bacReads)} reads` },
          { label: "Eukaryotes", value: fmtPct(pct(eukReads), 2), sub: `${fmt(eukReads)} reads` },
          { label: "Archaea", value: fmtPct(pct(archReads), 2), sub: `${fmt(archReads)} reads` },
          { label: "Other", value: fmtPct(pct(otherReads), 2), sub: `${fmt(otherReads)} reads` },
        ]}
      />
    </div>
  );
}

interface PathogenTableRowProps {
  t: SampleProfileEntry;
  classifiers: SampleProfile[];
  pathogenMap: Record<string | number, PathogenItem>;
}

function PathogenTableRow({ t, classifiers, pathogenMap }: Readonly<PathogenTableRowProps>) {
  const pathogenReason = pathogenMap[t.taxon_id]?.reason;
  return (
    <tr className="border-b border-gray-50">
      <td className="px-4 py-3 text-xs italic text-gray-800 font-medium">{t.name}</td>
      <td className="px-4 py-3 text-xs text-gray-500">{t.superkingdom ?? "—"}</td>
      <td className="px-4 py-3 text-xs text-gray-400">
        {pathogenReason ?? <span className="text-gray-300">{"—"}</span>}
      </td>
      {classifiers.map((clf) => {
        const entry = clf.profile?.find((e) => e.taxon_id === t.taxon_id);
        return (
          <td key={clf.classifier} className="px-4 py-3 text-xs tabular-nums">
            {entry ? (
              <span className="text-red-600 font-medium">{entry.abundance.toLocaleString()}</span>
            ) : (
              <span className="text-gray-300">{"—"}</span>
            )}
          </td>
        );
      })}
    </tr>
  );
}

interface KnownPathogensSectionProps {
  pathogenError: boolean;
  pathogenIds: Set<number>;
  classifiers: SampleProfile[];
  pathogenMap: Record<string | number, PathogenItem>;
}

function KnownPathogensSection({
  pathogenError,
  pathogenIds,
  classifiers,
  pathogenMap,
}: Readonly<KnownPathogensSectionProps>) {
  if (pathogenError) {
    return (
      <DataWarning message="Failed to load pathogen data — known pathogen detection unavailable." />
    );
  }
  if (pathogenIds.size === 0 || classifiers.length === 0) return null;
  const detected: SampleProfileEntry[] = [];
  const seen = new Set<number>();
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
        <svg className="w-3.5 h-3.5 text-red-500 flex-shrink-0" viewBox="0 0 16 16" fill="none">
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
          {detected.length} taxon{detected.length === 1 ? "" : "a"}
        </span>
      </div>
      <table className="w-full text-left border-collapse">
        <thead>
          <tr>
            {["Taxon", "Kingdom", "Notes"].map((h) => (
              <th
                key={h}
                className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100"
              >
                {h}
              </th>
            ))}
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
            <PathogenTableRow
              key={t.taxon_id}
              t={t}
              classifiers={classifiers}
              pathogenMap={pathogenMap}
            />
          ))}
        </tbody>
      </table>
    </section>
  );
}

function useReportSelection(sampleId: string) {
  const { selectedFor, addTaxon, removeTaxon } = useReportBuilder();
  const selectedIds = selectedFor(sampleId);
  return useMemo(
    () => ({
      selected: new Set(selectedIds),
      onToggle: (taxonId: number) =>
        selectedIds.includes(taxonId)
          ? removeTaxon(sampleId, taxonId)
          : addTaxon(sampleId, taxonId),
      onToggleAll: (taxonIds: number[]) => {
        const allSelected = taxonIds.every((id) => selectedIds.includes(id));
        if (allSelected) {
          for (const id of taxonIds) removeTaxon(sampleId, id);
        } else {
          for (const id of taxonIds) {
            if (!selectedIds.includes(id)) addTaxon(sampleId, id);
          }
        }
      },
    }),
    [selectedIds, sampleId, addTaxon, removeTaxon]
  );
}

interface SampleDetailContentProps {
  sampleId: string;
  onBack: () => void;
}

export default function SampleDetailContent({
  sampleId,
  onBack,
}: Readonly<SampleDetailContentProps>) {
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [metavalDisplayCount, setMetavalDisplayCount] = useState(10);

  useEffect(() => {
    setMetavalDisplayCount(10);
  }, [activeTab]);

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

  const { data: metavalResults = [], isError: metavalError } = useQuery({
    queryKey: ["metaval", sampleId],
    queryFn: () => getMetavalForSample(sampleId),
    enabled: !!sample,
  });

  const { data: ntcData, isError: ntcError } = useQuery({
    queryKey: ["ntcProfiles", sampleId],
    queryFn: () => getNtcProfiles(sampleId),
    enabled: !!sample,
  });
  const ntcProfiles = ntcData?.profiles ?? [];
  const contaminantConfig = ntcData?.contaminant_config ?? null;

  const { data: outbreakData, isError: outbreakError } = useQuery({
    queryKey: ["outbreaks", { windowDays: 14 }],
    queryFn: () => getOutbreaks(14),
  });

  const { data: pathogenList = [], isError: pathogenError } = useQuery({
    queryKey: ["pathogens"],
    queryFn: () => getPathogens(),
  });

  const outbreakTaxonIds = useMemo(
    () => new Set(outbreakData?.outbreaks?.map((o) => o.taxon_id) ?? []),
    [outbreakData]
  );

  const pathogenIds = useMemo(() => new Set(pathogenList.map((p) => p.taxon_id)), [pathogenList]);

  const pathogenMap = useMemo(
    () => Object.fromEntries(pathogenList.map((p) => [p.taxon_id, p])),
    [pathogenList]
  );

  useEffect(() => {
    if (!profile?.profiles?.length) return;
    const available = profile.profiles.map((p) => p.classifier);
    if (activeTab && available.includes(activeTab)) return;
    const requested = searchParams.get("classifier");
    const match = profile.profiles.find((p) => p.classifier === requested);
    setActiveTab(match ? match.classifier : profile.profiles[0].classifier);
  }, [profile, activeTab, searchParams]);

  // Hooks must run on every render before any early return — keep this block
  // above the loading/error guards.
  const reportSelection = useReportSelection(sampleId);

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

  const trana = sample?.trana as TranaQc | undefined;
  const isTrana = Boolean(trana);
  const qc = sample?.taxprofiler as TaxprofilerQc | undefined;
  const fp = qc?.fastp;
  const bt = qc?.bowtie2;
  const classifiers: SampleProfile[] = profile?.profiles ?? [];
  const sampleType = (sample?.sample_type as string | undefined) ?? "sample";

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <button
          onClick={onBack}
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
        <Badge type={sampleType as BadgeType} />
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-6">
        <section>
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
            QC metrics
          </p>
          {isTrana ? (
            <MetricStrip
              metrics={[
                {
                  label: "Total reads",
                  value: fmt(trana?.nanoplot_unprocessed?.number_of_reads),
                  sub: "before processing",
                },
                {
                  label: "Passed filter",
                  value: fmt(trana?.nanoplot_processed?.number_of_reads),
                  sub: "after processing",
                },
                {
                  label: "Mean read length",
                  value: trana?.nanoplot_processed?.mean_read_length?.toFixed(0) ?? "—",
                  sub: "bp",
                },
                {
                  label: "Mean quality",
                  value: trana?.nanoplot_processed?.mean_read_quality?.toFixed(1) ?? "—",
                  sub: "Q",
                },
                {
                  label: "Read N50",
                  value: fmt(trana?.nanoplot_processed?.read_length_n50),
                  sub: "bp",
                },
              ]}
            />
          ) : (
            <MetricStrip
              metrics={[
                {
                  label: "Total reads",
                  value: fp ? fmt(fp.total_reads_before_filtering) : "—",
                  sub: "before filtering",
                },
                {
                  label: "Passed filter",
                  value: fp ? fmt(fp.passed_filter_reads) : "—",
                  sub:
                    fp?.passed_filter_reads != null && fp.total_reads_before_filtering
                      ? `${fmtPct(
                          (fp.passed_filter_reads / fp.total_reads_before_filtering) * 100
                        )} of raw`
                      : "",
                },
                {
                  label: "Host removed",
                  value: bt ? fmtPct(bt.overall_alignment_rate) : "—",
                  sub: "bowtie2",
                },
                {
                  label: "Non-host reads",
                  value: bt ? fmt(bt.aligned_none) : "—",
                  sub: "bowtie2",
                },
                {
                  label: "Q20 rate",
                  value: fmtPct(fp?.q20_rate ? fp.q20_rate * 100 : null),
                  sub: "fastp",
                },
                {
                  label: "Q30 rate",
                  value: fmtPct(fp?.q30_rate ? fp.q30_rate * 100 : null),
                  sub: "fastp",
                },
              ]}
            />
          )}
        </section>

        {!isTrana && classifiers.length > 0 && (
          <section>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
              Classifier metrics
            </p>
            <div className="flex flex-col gap-2">
              {classifiers.map((clf) => (
                <ClassifierMetricsRow
                  key={clf.classifier}
                  clf={clf}
                  clfQc={qc?.classifiers?.[clf.classifier]}
                />
              ))}
            </div>
          </section>
        )}

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
                    const hasResults = metavalResults.some(
                      (r) => (r as { classifier?: string }).classifier === clf.classifier
                    );
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
              (() => {
                const filtered = metavalResults.filter(
                  (r) => (r as { classifier?: string }).classifier === activeTab
                );
                const displayed = filtered.slice(0, metavalDisplayCount);
                const hasMore = filtered.length > metavalDisplayCount;
                return (
                  <>
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
                          {displayed.map((r) => {
                            const taxonName = (r as { taxon_name?: string }).taxon_name ?? "";
                            return (
                              <tr key={r._id} className="border-t border-gray-50 hover:bg-gray-50">
                                <td className="px-4 py-2.5">
                                  <Link
                                    to={`/samples/${sampleId}/metaval/${r._id}`}
                                    className="text-xs italic text-gray-700 hover:text-blue-600 underline transition-colors"
                                  >
                                    {taxonName.replace(/^taxid_\d+_/, "").replace(/-/g, " ")}
                                  </Link>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    {hasMore && (
                      <div className="px-4 py-3 border-t border-gray-50">
                        <button
                          onClick={() => setMetavalDisplayCount((n) => n + 10)}
                          className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                        >
                          Load more ({filtered.length - metavalDisplayCount} remaining)
                        </button>
                      </div>
                    )}
                  </>
                );
              })()
            )}
          </section>
        )}

        <KnownPathogensSection
          pathogenError={pathogenError}
          pathogenIds={pathogenIds}
          classifiers={classifiers}
          pathogenMap={pathogenMap}
        />

        {(outbreakError || ntcError) &&
          (() => {
            let msg: string;
            if (outbreakError && ntcError) {
              msg =
                "Failed to load outbreak and NTC data — outbreak badges and NTC columns may be missing.";
            } else if (outbreakError) {
              msg = "Failed to load outbreak data — outbreak badges may be missing.";
            } else {
              msg = "Failed to load NTC data — NTC columns may be missing.";
            }
            return <DataWarning message={msg} />;
          })()}
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
                    metavalResults={metavalResults.map((r) => {
                      const rx = r as unknown as { taxon_id: number; classifier: string };
                      return { _id: r._id, taxon_id: rx.taxon_id, classifier: rx.classifier };
                    })}
                    sampleId={sampleId}
                    outbreakTaxonIds={outbreakTaxonIds}
                    ntcProfiles={ntcProfiles}
                    contaminantConfig={contaminantConfig}
                    pathogenIds={pathogenIds}
                    abundanceIsFraction={isTrana}
                    isNtc={sampleType !== "sample"}
                    selection={reportSelection}
                  />
                ) : null
              )}
          </section>
        )}
      </div>
    </div>
  );
}
