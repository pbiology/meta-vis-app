import { useQueries } from "@tanstack/react-query";
import { getProfile } from "../../api/samples";
import { getSubject, type Subject } from "../../api/subjects";
import { useCase, useCaseSamples } from "../../hooks/queries/useCases";
import { usePathogens } from "../../hooks/queries/useAlerts";
import { sampleKeys } from "../../hooks/queries/useSamples";
import { subjectKeys } from "../../hooks/queries/useSubjects";
import type { CaseListItem, CaseNote, Sample, SampleProfile } from "../../api/types";
import { compareBySampleType } from "../../utils/sampleOrdering";

// Shapes consumed by the report renderer. Cells carry reads and pct together
// so they can never drift out of sync; rows are keyed by sample_id (unique
// within a case) rather than sample_type (which isn't, e.g. two DNA samples).

export interface ReportSampleRow {
  sample_id: string;
  sample_type?: string;
  material?: string;
  classifiersAvailable: string[];
  fastp?: {
    total_reads_before_filtering?: number;
    passed_filter_reads?: number;
    q20_rate?: number;
    q30_rate?: number;
  };
  // Carried through so SamplesListSection can render the same fields the old
  // SampleInfoSection did without a re-fetch.
  sample_source?: string;
  order_date?: string;
  received_at?: string;
  sequencing_platform?: string;
  analysis_type?: string;
  case_id?: string;
  // Subject linkage so the SubjectsSection can resolve labels.
  subject_id?: string;
}

export interface ReportTaxonCell {
  reads: number;
  pct: number;
}

export interface ReportTaxon {
  taxon_id: number;
  name: string;
  rank?: string;
  superkingdom?: string | null;
  pathogen: boolean;
  // cells[sample_id][classifier] -> { reads, pct }. Missing keys = no detection.
  cells: Record<string, Record<string, ReportTaxonCell>>;
}

export interface PipelineConfig {
  pipeline_name?: string;
  pipeline_version?: string;
  nextflow?: string;
}

interface PipelineInfoShape {
  pipeline_configuration?: PipelineConfig;
}

export interface ReportData {
  generatedAt: string;
  caseDoc: CaseListItem;
  samples: ReportSampleRow[];
  classifiers: string[];
  subjects: Array<{ sample_id: string; subject: Subject | null }>;
  notes: CaseNote[];
  taxa: ReportTaxon[];
  taxprofilerInfo: PipelineConfig | undefined;
  metavalInfo: PipelineConfig | undefined;
}

interface UseReportDataResult {
  data: ReportData | undefined;
  isLoading: boolean;
  isError: boolean;
}

function readString(s: Sample, key: string): string | undefined {
  const v = (s as Record<string, unknown>)[key];
  return typeof v === "string" ? v : undefined;
}

function readNestedString(s: Sample, path: string[]): string | undefined {
  let cursor: unknown = s;
  for (const k of path) {
    if (!cursor || typeof cursor !== "object") return undefined;
    cursor = (cursor as Record<string, unknown>)[k];
  }
  return typeof cursor === "string" ? cursor : undefined;
}

function buildSampleRow(s: Sample, profiles: SampleProfile[]): ReportSampleRow {
  const tp = (s as { taxprofiler?: { fastp?: ReportSampleRow["fastp"] } }).taxprofiler;
  return {
    sample_id: s.sample_id,
    sample_type: readString(s, "sample_type"),
    material: readString(s, "material"),
    classifiersAvailable: profiles.map((p) => p.classifier).sort((a, b) => a.localeCompare(b)),
    fastp: tp?.fastp,
    sample_source: readString(s, "sample_source"),
    order_date: readString(s, "order_date"),
    received_at: readString(s, "received_at"),
    sequencing_platform:
      readNestedString(s, ["sequencing", "platform"]) ?? readString(s, "sequencing_platform"),
    analysis_type: readString(s, "analysis_type"),
    case_id: readString(s, "case_id"),
    subject_id: readString(s, "subject_id"),
  };
}

// Sum every entry in each classifier's profile, per sample. Used as the
// denominator for the "% non-host" cell value.
//
// Note on "non-host": taxprofiler emits profiles that have already been
// filtered against the host taxon list upstream, so summing every entry IS
// the non-host total. This matches the convention used in the in-app
// taxonomy table — keeping the same denominator means percentages on the
// report agree with what the user saw when ticking the taxon.
function buildTotals(
  samples: Sample[],
  profilesBySampleId: Map<string, SampleProfile[]>
): Map<string, Map<string, number>> {
  const totals = new Map<string, Map<string, number>>();
  for (const s of samples) {
    const inner = new Map<string, number>();
    for (const p of profilesBySampleId.get(s.sample_id) ?? []) {
      inner.set(p.classifier, p.profile?.reduce((sum, e) => sum + (e.abundance ?? 0), 0) ?? 0);
    }
    totals.set(s.sample_id, inner);
  }
  return totals;
}

type TaxonMeta = { name: string; rank?: string; superkingdom?: string | null };

function collectProfileCells(
  p: SampleProfile,
  sampleId: string,
  total: number,
  seen: Set<number>,
  meta: Map<number, TaxonMeta>,
  cells: Map<number, Record<string, Record<string, ReportTaxonCell>>>
): void {
  for (const e of p.profile ?? []) {
    if (!seen.has(e.taxon_id)) continue;
    if (!meta.has(e.taxon_id)) {
      meta.set(e.taxon_id, { name: e.name, rank: e.rank, superkingdom: e.superkingdom ?? null });
    }
    const reads = e.abundance ?? 0;
    const pct = total > 0 ? (reads / total) * 100 : 0;
    const taxonCells = cells.get(e.taxon_id) ?? {};
    const sampleCells = taxonCells[sampleId] ?? {};
    sampleCells[p.classifier] = { reads, pct };
    taxonCells[sampleId] = sampleCells;
    cells.set(e.taxon_id, taxonCells);
  }
}

function buildTaxa(
  selectionsBySampleId: Record<string, number[]>,
  samples: Sample[],
  profilesBySampleId: Map<string, SampleProfile[]>,
  pathogenIds: Set<number>,
  totals: Map<string, Map<string, number>>
): ReportTaxon[] {
  // Union of all selected taxon_ids in the case. Order is the order the user
  // ticked them, by walking samples in their canonical order then preserving
  // selection order within each sample.
  const wantedOrder: number[] = [];
  const seen = new Set<number>();
  for (const s of samples) {
    for (const id of selectionsBySampleId[s.sample_id] ?? []) {
      if (!seen.has(id)) {
        seen.add(id);
        wantedOrder.push(id);
      }
    }
  }
  if (wantedOrder.length === 0) return [];

  // Resolve metadata (name, rank, ...) lazily — first sighting in any sample's
  // profile wins. This avoids a second metadata fetch and matches the in-app
  // taxonomy table's behaviour.
  const meta = new Map<number, TaxonMeta>();
  const cells = new Map<number, Record<string, Record<string, ReportTaxonCell>>>();
  for (const s of samples) {
    for (const p of profilesBySampleId.get(s.sample_id) ?? []) {
      const total = totals.get(s.sample_id)?.get(p.classifier) ?? 0;
      collectProfileCells(p, s.sample_id, total, seen, meta, cells);
    }
  }

  return wantedOrder.map((taxon_id) => {
    const m = meta.get(taxon_id);
    return {
      taxon_id,
      name: m?.name ?? `Taxon ${taxon_id}`,
      rank: m?.rank,
      superkingdom: m?.superkingdom ?? null,
      pathogen: pathogenIds.has(taxon_id),
      cells: cells.get(taxon_id) ?? {},
    };
  });
}

function formatReportDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function useReportData(
  caseId: string,
  selectionsBySampleId: Record<string, number[]>
): UseReportDataResult {
  const caseQ = useCase(caseId);
  const samplesQ = useCaseSamples(caseId);
  const pathogensQ = usePathogens();

  const samples = samplesQ.data ?? [];

  const profileQueries = useQueries({
    queries: samples.map((s) => {
      const id = (s._id ?? s.sample_id) as string;
      return {
        queryKey: sampleKeys.profile(id),
        queryFn: () => getProfile(id),
        enabled: Boolean(id),
      };
    }),
  });

  const subjectIds = Array.from(
    new Set(samples.map((s) => readString(s, "subject_id")).filter((v): v is string => Boolean(v)))
  );
  const subjectQueries = useQueries({
    queries: subjectIds.map((id) => ({
      queryKey: subjectKeys.detail(id),
      queryFn: () => getSubject(id),
    })),
  });

  const isLoading =
    caseQ.isLoading ||
    samplesQ.isLoading ||
    pathogensQ.isLoading ||
    profileQueries.some((q) => q.isLoading) ||
    subjectQueries.some((q) => q.isLoading);

  const isError =
    caseQ.isError ||
    samplesQ.isError ||
    pathogensQ.isError ||
    profileQueries.some((q) => q.isError);

  if (isLoading || isError || !caseQ.data || !samplesQ.data) {
    return { data: undefined, isLoading, isError };
  }

  // Per-sample profiles, keyed by canonical sample_id for downstream lookups.
  const profilesBySampleId = new Map<string, SampleProfile[]>();
  samples.forEach((s, i) => {
    profilesBySampleId.set(s.sample_id, profileQueries[i]?.data?.profiles ?? []);
  });

  const orderedSamples = [...samples].sort(compareBySampleType);

  const sampleRows: ReportSampleRow[] = orderedSamples.map((s) =>
    buildSampleRow(s, profilesBySampleId.get(s.sample_id) ?? [])
  );

  // Canonical column order for the whole report — union of all classifiers
  // observed across the case, alphabetical so columns don't shift card-to-card.
  const classifierSet = new Set<string>();
  for (const profiles of profilesBySampleId.values()) {
    for (const p of profiles) classifierSet.add(p.classifier);
  }
  const classifiers = Array.from(classifierSet).sort((a, b) => a.localeCompare(b));

  const subjectBy = new Map<string, Subject>();
  subjectIds.forEach((id, i) => {
    const s = subjectQueries[i]?.data;
    if (s) subjectBy.set(id, s);
  });

  const subjects = orderedSamples.map((s) => {
    const sid = readString(s, "subject_id");
    return {
      sample_id: s.sample_id,
      subject: sid ? (subjectBy.get(sid) ?? null) : null,
    };
  });

  const pathogenIds = new Set((pathogensQ.data ?? []).map((p) => p.taxon_id));
  const totals = buildTotals(orderedSamples, profilesBySampleId);
  const taxa = buildTaxa(
    selectionsBySampleId,
    orderedSamples,
    profilesBySampleId,
    pathogenIds,
    totals
  );

  const caseDoc = caseQ.data as CaseListItem;
  const asPipelineConfig = (raw: unknown): PipelineConfig | undefined => {
    const info = raw as PipelineInfoShape | undefined;
    return info?.pipeline_configuration;
  };

  return {
    data: {
      generatedAt: formatReportDate(new Date()),
      caseDoc,
      samples: sampleRows,
      classifiers,
      subjects,
      notes: caseDoc.notes ?? [],
      taxa,
      taxprofilerInfo: asPipelineConfig(caseDoc.pipeline_info),
      metavalInfo: asPipelineConfig(caseDoc.metaval_pipeline_info),
    },
    isLoading: false,
    isError: false,
  };
}
