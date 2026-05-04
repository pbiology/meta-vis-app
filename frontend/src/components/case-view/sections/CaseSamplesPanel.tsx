import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { PathogenItem, Sample } from "../../../api/types";
import Badge from "../../Badge";
import { fmt } from "../../../utils/format";

const FILTERS = ["All", "Sample", "Controls"] as const;
type Filter = (typeof FILTERS)[number];

interface CaseSamplesPanelProps {
  samples: Sample[];
  pathogenMap: Record<number, PathogenItem>;
}

interface TaxprofilerFastp {
  fastp?: { total_reads_before_filtering?: number };
}
interface TranaNanoplot {
  nanoplot_unprocessed?: { number_of_reads?: number };
}

export default function CaseSamplesPanel({
  samples,
  pathogenMap,
}: Readonly<CaseSamplesPanelProps>) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>("All");

  const filtered = useMemo(() => {
    if (filter === "Sample") return samples.filter((s) => s.sample_type === "sample");
    if (filter === "Controls")
      return samples.filter(
        (s) => s.sample_type === "negative_ctrl" || s.sample_type === "positive_ctrl"
      );
    return samples;
  }, [samples, filter]);

  return (
    <section className="bg-white border border-gray-100 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900 m-0">
          Samples · {samples.length}
        </h3>
        <div className="ml-auto flex gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                filter === f
                  ? "bg-gray-900 text-white font-medium"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      <table className="w-full text-left border-collapse">
        <thead>
          <tr>
            {["Sample ID", "Material", "Type", "Source", "Total reads"].map((h) => (
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
          {filtered.map((s) => {
            const trana = s.trana as TranaNanoplot | undefined;
            const tp = s.taxprofiler as TaxprofilerFastp | undefined;
            const taxonIds = (s.all_taxon_ids as number[] | undefined) ?? [];
            const flagged = taxonIds.filter((id) => id in pathogenMap);
            return (
              <tr
                key={s._id as string}
                onClick={() => navigate(`/samples/${s._id}`)}
                className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
              >
                <td className="px-4 py-3 font-mono text-xs text-gray-700">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span>{s.sample_id ?? "—"}</span>
                    {flagged.map((id) => (
                      <Link
                        key={id}
                        to={`/taxa/${id}`}
                        title={pathogenMap[id].taxon_name}
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs bg-red-50 text-red-600 font-medium hover:bg-red-100 transition-colors font-sans not-italic"
                      >
                        {pathogenMap[id].taxon_name}
                      </Link>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {(s.material as string | undefined) ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <Badge type={(s.sample_type as string | undefined) ?? "sample"} />
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {(s.sample_source as string | undefined) ?? "—"}
                </td>
                <td className="px-4 py-3 text-xs text-gray-700">
                  {fmt(
                    trana
                      ? trana.nanoplot_unprocessed?.number_of_reads
                      : tp?.fastp?.total_reads_before_filtering
                  )}
                </td>
              </tr>
            );
          })}
          {filtered.length === 0 && (
            <tr>
              <td colSpan={5} className="px-4 py-10 text-center text-sm text-gray-400">
                No samples match this filter.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
