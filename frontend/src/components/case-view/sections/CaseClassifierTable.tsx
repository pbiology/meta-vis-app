import type { Sample } from "../../../api/types";
import { fmt, fmtPct } from "../../../utils/format";
import type { Classifier } from "./CaseClassifiers";

interface TopTaxon {
  name: string;
  superkingdom?: string;
  pct?: number;
  abundance?: number;
}

interface SampleClassifierQc {
  pct_unclassified?: number;
  num_species?: number;
  num_genera?: number;
}

interface TaxprofilerInfo {
  classifiers?: Record<string, SampleClassifierQc>;
}

interface TranaInfo {
  nanoplot_unprocessed?: { number_of_reads?: number };
}

const KINGDOM_COLOR_CLASSES: Record<string, string> = {
  Bacteria: "bg-blue-400",
  Viruses: "bg-red-400",
  Eukaryota: "bg-amber-400",
  Archaea: "bg-purple-400",
};

function superkingdomColor(kingdom: string | undefined): string {
  return KINGDOM_COLOR_CLASSES[kingdom ?? ""] ?? "bg-gray-300";
}

interface TopTaxaCellProps {
  taxa: TopTaxon[];
}

function TopTaxaCell({ taxa }: Readonly<TopTaxaCellProps>) {
  return (
    <td className="px-4 py-1.5">
      <div className="flex flex-col gap-0">
        {taxa.map((t) => (
          <span
            key={t.name}
            className="flex items-center gap-1"
            style={{ fontSize: "11px", lineHeight: "1.4" }}
          >
            <span
              className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${superkingdomColor(t.superkingdom)}`}
            />
            <span className="text-gray-600 italic truncate max-w-36">{t.name}</span>
            {t.pct != null && (
              <span className="text-gray-400 flex-shrink-0">{t.pct.toFixed(1)}%</span>
            )}
          </span>
        ))}
      </div>
    </td>
  );
}

interface CaseClassifierTableProps {
  activeClassifier: Classifier;
  samples: Sample[];
  isTrana: boolean;
  onSelectSample: (sampleId: string) => void;
}

export default function CaseClassifierTable({
  activeClassifier,
  samples,
  isTrana,
  onSelectSample,
}: Readonly<CaseClassifierTableProps>) {
  const headers = isTrana
    ? ["Sample", "Reads (raw)", "Top taxa"]
    : ["Sample", "Unclassified", "Host", "Species", "Genera", "Positive control", "Top taxa"];

  return (
    <table className="w-full text-left border-collapse">
      <thead>
        <tr>
          {headers.map((h) => (
            <th
              key={h}
              className="px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-gray-400 border-b border-gray-100 whitespace-nowrap"
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {samples.map((s) => {
          const topTaxaMap = s.top_taxa as Record<string, TopTaxon[]> | undefined;
          const topTaxa: TopTaxon[] = topTaxaMap?.[activeClassifier.name] ?? [];
          const trana = s.trana as TranaInfo | undefined;
          const tp = s.taxprofiler as TaxprofilerInfo | undefined;
          const hostPct = s.host_pct as Record<string, number> | undefined;
          const spikeInMap = s.spike_in_taxa as Record<string, TopTaxon[]> | undefined;
          const clfQc = tp?.classifiers?.[activeClassifier.name];
          const spikeIn: TopTaxon[] = spikeInMap?.[activeClassifier.name] ?? [];
          const sampleId = s._id as string;

          return (
            <tr
              key={sampleId}
              onClick={() => onSelectSample(sampleId)}
              className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
            >
              <td className="px-4 py-1.5 font-mono text-xs text-gray-700">{s.sample_id ?? "—"}</td>
              {isTrana ? (
                <>
                  <td className="px-4 py-1.5 text-xs text-gray-700">
                    {fmt(trana?.nanoplot_unprocessed?.number_of_reads)}
                  </td>
                  <TopTaxaCell taxa={topTaxa} />
                </>
              ) : (
                <>
                  <td className="px-4 py-1.5 text-xs text-gray-700">
                    {fmtPct(clfQc?.pct_unclassified)}
                  </td>
                  <td className="px-4 py-1.5 text-xs text-gray-700">
                    {hostPct?.[activeClassifier.name] == null
                      ? "—"
                      : `${hostPct[activeClassifier.name]}%`}
                  </td>
                  <td className="px-4 py-1.5 text-xs text-gray-700">{fmt(clfQc?.num_species)}</td>
                  <td className="px-4 py-1.5 text-xs text-gray-700">{fmt(clfQc?.num_genera)}</td>
                  <td className="px-4 py-1.5 text-xs">
                    {spikeIn.length > 0 ? (
                      <div className="flex flex-col gap-0.5">
                        {spikeIn.map((t) => (
                          <span key={t.name} className="text-gray-600 italic">
                            {t.name}
                            {t.pct != null && (
                              <span className="not-italic text-gray-400 ml-1">
                                {t.pct}% ({t.abundance?.toLocaleString()})
                              </span>
                            )}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-gray-300">Not detected</span>
                    )}
                  </td>
                  <TopTaxaCell taxa={topTaxa} />
                </>
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
