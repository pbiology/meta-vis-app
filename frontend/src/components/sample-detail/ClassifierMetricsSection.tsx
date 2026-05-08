import { MetricStrip } from "../MetricStrip";
import { fmt, fmtPct } from "../../utils/format";
import { TAXON_ID_HUMAN } from "../../utils/taxonomy";
import type { SampleProfile } from "../../api/types";
import type { ClassifierQcStats, SuperkingdomKey, TaxprofilerQc } from "./types";

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

interface ClassifierMetricsSectionProps {
  classifiers: SampleProfile[];
  qc: TaxprofilerQc | undefined;
}

export default function ClassifierMetricsSection({
  classifiers,
  qc,
}: Readonly<ClassifierMetricsSectionProps>) {
  if (classifiers.length === 0) return null;
  return (
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
  );
}
