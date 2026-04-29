import { useQuery } from "@tanstack/react-query";
import { getSample, getProfile } from "../../api/samples";
import { getCase } from "../../api/cases";
import { getPathogens } from "../../api/alerts";
import { getSubject, type Subject } from "../../api/subjects";
import type { Sample, SampleProfile, CaseListItem, CaseNote } from "../../api/types";

// Shape consumed by <Report>. Keep it presentation-friendly: dates as ISO strings,
// numbers as numbers, optional fields nullable so sections can render `—`.
export interface ReportTaxon {
  taxon_id: number;
  name: string;
  rank?: string;
  superkingdom?: string | null;
  pathogen: boolean;
  // Per-classifier abundance (raw reads) and percentage of non-host.
  abundance: Record<string, number>;
  pct: Record<string, number>;
}

export interface ReportData {
  generatedAt: string;
  sample: Sample;
  subject: Subject | null;
  taxa: ReportTaxon[];
  notes: CaseNote[];
  sampleNote: string | null;
  // Provenance is derived from whatever pipeline metadata is on the case;
  // sections render `—` for fields that aren't populated.
  pipelineInfo: unknown;
}

interface UseReportDataResult {
  data: ReportData | undefined;
  isLoading: boolean;
  isError: boolean;
}

function buildTaxa(
  profiles: SampleProfile[],
  taxonIds: number[],
  pathogenIds: Set<number>
): ReportTaxon[] {
  if (taxonIds.length === 0) return [];

  // Total non-host reads per classifier — used to compute pct for each taxon.
  // Mirrors the same exclusion logic the taxonomy table uses (host/unclassified
  // are dropped) but at this layer the report consumer has already opted in to
  // a specific list of taxa, so we just sum every entry.
  const totalsByClassifier: Record<string, number> = {};
  for (const p of profiles) {
    totalsByClassifier[p.classifier] = p.profile?.reduce((s, e) => s + (e.abundance ?? 0), 0) ?? 0;
  }

  const wanted = new Set(taxonIds);
  const merged = new Map<number, ReportTaxon>();
  for (const p of profiles) {
    for (const e of p.profile ?? []) {
      if (!wanted.has(e.taxon_id)) continue;
      let t = merged.get(e.taxon_id);
      if (!t) {
        t = {
          taxon_id: e.taxon_id,
          name: e.name,
          rank: e.rank,
          superkingdom: e.superkingdom ?? null,
          pathogen: pathogenIds.has(e.taxon_id),
          abundance: {},
          pct: {},
        };
        merged.set(e.taxon_id, t);
      }
      t.abundance[p.classifier] = e.abundance ?? 0;
      const total = totalsByClassifier[p.classifier] ?? 0;
      t.pct[p.classifier] = total > 0 ? ((e.abundance ?? 0) / total) * 100 : 0;
    }
  }

  // Preserve the user's selection order so the report matches what they ticked.
  return taxonIds.map((id) => merged.get(id)).filter((t): t is ReportTaxon => Boolean(t));
}

export function useReportData(sampleId: string, taxonIds: number[]): UseReportDataResult {
  const sampleQ = useQuery({
    queryKey: ["sample", sampleId],
    queryFn: () => getSample(sampleId),
  });
  const profileQ = useQuery({
    queryKey: ["profile", sampleId],
    queryFn: () => getProfile(sampleId),
  });
  const pathogensQ = useQuery({ queryKey: ["pathogens"], queryFn: getPathogens });

  const caseId = sampleQ.data?.case_id;
  const caseQ = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => getCase(caseId as string),
    enabled: Boolean(caseId),
  });

  const subjectId = (sampleQ.data?.subject_id as string | undefined) ?? null;
  const subjectQ = useQuery({
    queryKey: ["subject", subjectId],
    queryFn: () => getSubject(subjectId as string),
    enabled: Boolean(subjectId),
  });

  const isLoading =
    sampleQ.isLoading ||
    profileQ.isLoading ||
    pathogensQ.isLoading ||
    (Boolean(caseId) && caseQ.isLoading) ||
    (Boolean(subjectId) && subjectQ.isLoading);

  const isError = sampleQ.isError || profileQ.isError || pathogensQ.isError || caseQ.isError;

  if (isLoading || isError || !sampleQ.data || !profileQ.data) {
    return { data: undefined, isLoading, isError };
  }

  const pathogenIds = new Set((pathogensQ.data ?? []).map((p) => p.taxon_id));
  const taxa = buildTaxa(profileQ.data.profiles ?? [], taxonIds, pathogenIds);
  const caseDoc = caseQ.data as CaseListItem | undefined;

  const data: ReportData = {
    generatedAt: new Date().toISOString(),
    sample: sampleQ.data,
    subject: subjectQ.data ?? null,
    taxa,
    notes: caseDoc?.notes ?? [],
    sampleNote: ((sampleQ.data.review as { notes?: string } | undefined)?.notes ?? null) || null,
    pipelineInfo:
      caseDoc?.pipeline_info ??
      (sampleQ.data.taxprofiler as { pipeline_info?: unknown } | undefined)?.pipeline_info,
  };

  return { data, isLoading: false, isError: false };
}
