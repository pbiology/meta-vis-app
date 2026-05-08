import { useEffect, useMemo, useState } from "react";
import MetavalDetailsContent from "./MetavalDetailsContent";
import TaxonDetailContent from "./TaxonDetailContent";
import Badge, { type BadgeType } from "./Badge";
import DataWarning from "./DataWarning";
import { useReportBuilder } from "../context/ReportBuilderContext";
import { useAuth } from "../context/AuthContext";
import { useNtcProfiles, useSample, useSampleProfile } from "../hooks/queries/useSamples";
import { useMetavalForSample } from "../hooks/queries/useMetaval";
import { useOutbreaks, usePathogens } from "../hooks/queries/useAlerts";
import type { SampleProfile } from "../api/types";
import SampleQcSection from "./sample-detail/SampleQcSection";
import ClassifierMetricsSection from "./sample-detail/ClassifierMetricsSection";
import SampleMetavalSection from "./sample-detail/SampleMetavalSection";
import SampleKnownPathogensSection from "./sample-detail/SampleKnownPathogensSection";
import SampleTaxonomySection from "./sample-detail/SampleTaxonomySection";
import type { TaxprofilerQc, TranaQc } from "./sample-detail/types";

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
  // Optional human-readable key used for report-builder selections; defaults
  // to `sampleId` when not provided. CaseView passes the canonical sample_id
  // here while keeping `sampleId` as the Mongo _id used for API calls.
  selectionKey?: string;
  onBack: () => void;
}

function auxDataWarningMessage(outbreakError: boolean, ntcError: boolean): string | null {
  if (outbreakError && ntcError) {
    return "Failed to load outbreak and NTC data — outbreak badges and NTC columns may be missing.";
  }
  if (outbreakError) {
    return "Failed to load outbreak data — outbreak badges may be missing.";
  }
  if (ntcError) {
    return "Failed to load NTC data — NTC columns may be missing.";
  }
  return null;
}

export default function SampleDetailContent({
  sampleId,
  selectionKey,
  onBack,
}: Readonly<SampleDetailContentProps>) {
  const reportKey = selectionKey ?? sampleId;
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [activeMetavalId, setActiveMetavalId] = useState<string | null>(null);
  const [activeTaxonId, setActiveTaxonId] = useState<number | null>(null);

  const { data: sample, isLoading: sampleLoading, isError: sampleError } = useSample(sampleId);
  const {
    data: profile,
    isLoading: profileLoading,
    isError: profileError,
  } = useSampleProfile(sampleId);
  const { data: metavalResults = [], isError: metavalError } = useMetavalForSample(sampleId, {
    enabled: !!sample,
  });
  const { data: ntcData, isError: ntcError } = useNtcProfiles(sampleId, { enabled: !!sample });
  const { data: outbreakData, isError: outbreakError } = useOutbreaks(14);
  const { data: pathogenList = [], isError: pathogenError } = usePathogens();

  const ntcProfiles = ntcData?.profiles ?? [];
  const contaminantConfig = ntcData?.contaminant_config ?? null;

  const outbreakTaxonIds = useMemo(
    () => new Set(outbreakData?.outbreaks?.map((o) => o.taxon_id) ?? []),
    [outbreakData]
  );
  const pathogenIds = useMemo(() => new Set(pathogenList.map((p) => p.taxon_id)), [pathogenList]);
  const pathogenMap = useMemo(
    () => Object.fromEntries(pathogenList.map((p) => [p.taxon_id, p])),
    [pathogenList]
  );

  // Pick the first available classifier as the active tab; switch when the
  // profile changes (e.g. cross-sample navigation) and the prior tab no longer
  // exists for this sample.
  useEffect(() => {
    if (!profile?.profiles?.length) return;
    const available = profile.profiles.map((p) => p.classifier);
    if (activeTab && available.includes(activeTab)) return;
    setActiveTab(profile.profiles[0].classifier);
  }, [profile, activeTab]);

  // Hooks must run on every render before any early return — keep this block
  // above the loading/error guards.
  const { role } = useAuth();
  const baseReportSelection = useReportSelection(reportKey);
  // Readers see no checkboxes in the taxonomy table; passing `undefined`
  // makes TaxonomyTable hide both the header and per-row checkbox cells.
  const reportSelection = role === "reader" ? undefined : baseReportSelection;

  if (activeMetavalId) {
    return (
      <MetavalDetailsContent metavalId={activeMetavalId} onBack={() => setActiveMetavalId(null)} />
    );
  }
  if (activeTaxonId !== null) {
    return (
      <TaxonDetailContent
        taxonId={String(activeTaxonId)}
        sampleId={reportKey}
        onBack={() => setActiveTaxonId(null)}
      />
    );
  }
  if (sampleLoading || profileLoading) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">
        Loading&hellip;
      </div>
    );
  }
  if (sampleError || profileError) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-red-500">
        Failed to load sample.
      </div>
    );
  }

  const trana = sample?.trana as TranaQc | undefined;
  const isTrana = Boolean(trana);
  const qc = sample?.taxprofiler as TaxprofilerQc | undefined;
  const fp = qc?.fastp;
  const bt = qc?.bowtie2;
  const classifiers: SampleProfile[] = profile?.profiles ?? [];
  const sampleType = (sample?.sample_type as string | undefined) ?? "sample";
  const auxWarning = auxDataWarningMessage(Boolean(outbreakError), Boolean(ntcError));

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
        <SampleQcSection isTrana={isTrana} trana={trana} fp={fp} bt={bt} />

        {!isTrana && <ClassifierMetricsSection classifiers={classifiers} qc={qc} />}

        {!isTrana && metavalError && (
          <DataWarning message="Failed to load metaval data — metaval results may be missing." />
        )}
        {!isTrana && (
          <SampleMetavalSection
            classifiers={classifiers}
            metavalResults={metavalResults}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            onSelectMetaval={setActiveMetavalId}
          />
        )}

        <SampleKnownPathogensSection
          pathogenError={pathogenError}
          pathogenIds={pathogenIds}
          classifiers={classifiers}
          pathogenMap={pathogenMap}
        />

        {auxWarning && <DataWarning message={auxWarning} />}

        <SampleTaxonomySection
          classifiers={classifiers}
          qc={qc}
          metavalResults={metavalResults}
          sampleId={sampleId}
          outbreakTaxonIds={outbreakTaxonIds}
          ntcProfiles={ntcProfiles}
          contaminantConfig={contaminantConfig}
          pathogenIds={pathogenIds}
          isTrana={isTrana}
          sampleType={sampleType}
          selection={reportSelection}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onSelectTaxon={setActiveTaxonId}
        />
      </div>
    </div>
  );
}
