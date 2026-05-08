import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useNtcContaminantAlerts, useNtcTrends } from "../../hooks/queries/useNtc";
import KingdomBreakdownChart from "./KingdomBreakdownChart";
import ReadCountChart from "./ReadCountChart";
import RecurringTaxaChart from "./RecurringTaxaChart";
import NtcContaminantBanner from "./NtcContaminantBanner";
import NtcFiltersBar, { type NtcPipelineOption } from "./NtcFiltersBar";
import { useContainerWidth } from "./chartUtils";

const PIPELINE_TO_ANALYSIS: Record<string, string> = {
  taxprofiler: "shotgun",
  trana: "amplicon",
};

const PIPELINE_OPTIONS: NtcPipelineOption[] = [
  { value: "taxprofiler", label: "Taxprofiler" },
  { value: "trana", label: "Trana" },
];

export default function NtcTrendsContent() {
  const { preferences } = useAuth();
  const visibleAnalysis = preferences?.visible_analysis_types ?? ["shotgun", "amplicon"];
  const availablePipelines = useMemo(
    () => PIPELINE_OPTIONS.filter((p) => visibleAnalysis.includes(PIPELINE_TO_ANALYSIS[p.value])),
    [visibleAnalysis]
  );

  const [material, setMaterial] = useState("DNA");
  const [pipeline, setPipeline] = useState(availablePipelines[0]?.value ?? "taxprofiler");
  const [windowDays, setWindowDays] = useState(90);
  const [minReads, setMinReads] = useState(3);
  const [minAbundance, setMinAbundance] = useState(0.001);
  const [minCasePct, setMinCasePct] = useState(10);

  // If the user's preferences change such that the active pipeline becomes
  // unavailable, switch to the first available one. Without this, the page
  // can render filters that don't match the underlying data fetch.
  useEffect(() => {
    if (!availablePipelines.some((p) => p.value === pipeline) && availablePipelines.length > 0) {
      setPipeline(availablePipelines[0].value);
    }
  }, [availablePipelines, pipeline]);

  const isTrana = pipeline === "trana";
  const trendsQ = useNtcTrends({
    material: isTrana ? "DNA" : material,
    windowDays,
    minReads: isTrana ? minAbundance : minReads,
    minCasePct: minCasePct / 100,
    pipeline,
  });
  const alertsQ = useNtcContaminantAlerts();

  const data = trendsQ.data ?? null;
  const contaminantAlerts = alertsQ.data?.alerts ?? [];

  const [readCountRef, readCountWidth] = useContainerWidth();
  const [kingdomRef, kingdomWidth] = useContainerWidth();
  const [recurringRef, recurringWidth] = useContainerWidth();

  return (
    <div className="flex flex-col h-full">
      <NtcFiltersBar
        material={material}
        pipeline={pipeline}
        windowDays={windowDays}
        minReads={minReads}
        minAbundance={minAbundance}
        minCasePct={minCasePct}
        availablePipelines={availablePipelines}
        onMaterialChange={setMaterial}
        onPipelineChange={setPipeline}
        onWindowDaysChange={setWindowDays}
        onMinReadsChange={setMinReads}
        onMinAbundanceChange={setMinAbundance}
        onMinCasePctChange={setMinCasePct}
      />

      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-6">
        {trendsQ.isLoading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">
            Loading…
          </div>
        )}
        {trendsQ.isError && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">
            Failed to load NTC trends.
          </div>
        )}

        {!trendsQ.isLoading && !trendsQ.isError && data && (
          <>
            <NtcContaminantBanner alerts={contaminantAlerts} />

            <p className="text-xs text-gray-400">
              {data.total_ntcs} {material} NTC
              {data.total_ntcs !== 1 ? "s" : ""} in the last {windowDays} days
              {data.recurring_taxa.length > 0 ? (
                <span className="text-amber-500 font-medium ml-1">
                  · {data.recurring_taxa.length} recurring{" "}
                  {data.recurring_taxa.length === 1 ? "taxon" : "taxa"}
                </span>
              ) : (
                <span className="text-green-500 font-medium ml-1">· no recurring taxa</span>
              )}
            </p>

            <section ref={kingdomRef} className="bg-white border border-gray-100 rounded-xl p-4">
              <h2 className="text-xs font-medium text-gray-600 mb-3">Kingdom breakdown</h2>
              <p className="text-xs text-gray-400 mb-3">
                Classified reads per NTC by superkingdom. Host and structural nodes excluded.
              </p>
              {kingdomWidth > 0 && (
                <KingdomBreakdownChart data={data.kingdom_breakdown} width={kingdomWidth - 32} />
              )}
            </section>

            <section ref={readCountRef} className="bg-white border border-gray-100 rounded-xl p-4">
              <h2 className="text-xs font-medium text-gray-600 mb-3">Total classified reads</h2>
              <p className="text-xs text-gray-400 mb-3">
                Each dot is one NTC. Dashed line at 1 000 reads.
              </p>
              {readCountWidth > 0 && (
                <ReadCountChart
                  data={data.read_counts}
                  width={readCountWidth - 32}
                  isFraction={isTrana}
                />
              )}
            </section>

            <section ref={recurringRef} className="bg-white border border-gray-100 rounded-xl p-4">
              <div className="flex items-center justify-between mb-1">
                <h2 className="text-xs font-medium text-gray-600">Recurring taxa</h2>
                <span className="text-xs text-gray-400">
                  ≥ {minCasePct}% of cases ·{" "}
                  {isTrana
                    ? `> ${(minAbundance * 100).toFixed(1)}% abundance · emu`
                    : `> ${minReads} reads · kraken2`}
                </span>
              </div>
              <p className="text-xs text-gray-400 mb-3">
                Taxa present in ≥ {data.min_case_count} of {data.total_ntcs} NTCs in this window.
              </p>
              {recurringWidth > 0 && (
                <RecurringTaxaChart
                  taxa={data.recurring_taxa}
                  width={recurringWidth - 32}
                  isFraction={isTrana}
                />
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
