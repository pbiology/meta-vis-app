import { useMemo, useState } from "react";
import type { PathogenItem, Sample } from "../../../api/types";
import Badge from "../../Badge";
import DataWarning from "../../DataWarning";
import SampleDeltaBadge from "./SampleDeltaBadge";
import { fmt } from "../../../utils/format";

const FILTERS = ["All", "Sample", "Controls"] as const;
type Filter = (typeof FILTERS)[number];

/**
 * Announce clinical samples whose material has no usable negative control.
 *
 * Contaminant flagging compares a sample against NTCs from the same run *and
 * the same material* (see `routers/samples.py`), and silently does nothing
 * when there are none — so an analysis with a failed NTC looks exactly like
 * one with a clean NTC. Material is part of the check because a DNA-only NTC
 * leaves RNA samples uncovered; a warning that ignored it would be wrong on
 * every mixed-material case.
 */
export function ntcCoverageWarning(samples: Sample[]): string | null {
  // Coverage is only decidable per material, so a sample without one is left
  // out rather than described with a material name it does not have. The
  // ingest models make material mandatory, so this cannot happen in practice.
  const materials = new Set(
    samples
      .filter((s) => s.sample_type === "sample" && typeof s.material === "string")
      .map((s) => s.material as string)
  );

  const missing: string[] = [];
  const empty: string[] = [];
  // Sorted so the warning names materials in a stable order; localeCompare
  // rather than the default sort, which orders by UTF-16 code unit.
  for (const material of [...materials].sort((a, b) => a.localeCompare(b))) {
    const ntcs = samples.filter(
      (s) => s.sample_type === "negative_ctrl" && s.material === material
    );
    if (ntcs.length === 0) {
      missing.push(material);
    } else if (ntcs.every((s) => s.has_profile_data === false)) {
      // Only claimed when the server said so explicitly — an older response
      // without the field must not be reported as an empty control.
      empty.push(material);
    }
  }

  const parts: string[] = [];
  if (missing.length > 0) {
    parts.push(
      `No ${missing.join(" or ")} negative control in this analysis — ` +
        `contaminant flagging is unavailable for ${missing.join(" and ")} samples.`
    );
  }
  if (empty.length > 0) {
    parts.push(
      `The ${empty.join(" and ")} negative control produced no classifier data — ` +
        `contaminant flagging is unavailable for ${empty.join(" and ")} samples.`
    );
  }
  return parts.length > 0 ? parts.join(" ") : null;
}

interface CaseSamplesPanelProps {
  samples: Sample[];
  pathogenMap: Record<number, PathogenItem>;
  onSelectSample: (sampleId: string) => void;
}

export default function CaseSamplesPanel({
  samples,
  pathogenMap,
  onSelectSample,
}: Readonly<CaseSamplesPanelProps>) {
  const [filter, setFilter] = useState<Filter>("All");

  const ntcWarning = useMemo(() => ntcCoverageWarning(samples), [samples]);

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
      {ntcWarning && (
        <div className="px-4 pt-3">
          <DataWarning message={ntcWarning} />
        </div>
      )}
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
            const taxonIds = (s.all_taxon_ids as number[] | undefined) ?? [];
            const flagged = taxonIds.filter((id) => id in pathogenMap);
            return (
              <tr
                key={s._id as string}
                onClick={() => onSelectSample(s._id as string)}
                className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
              >
                <td className="px-4 py-3 font-mono text-xs text-gray-700">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span>{s.sample_id ?? "—"}</span>
                    {flagged.map((id) => (
                      <a
                        key={id}
                        href={`/taxa/${id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={pathogenMap[id].taxon_name}
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs bg-red-50 text-red-600 font-medium hover:bg-red-100 transition-colors font-sans not-italic"
                      >
                        {pathogenMap[id].taxon_name}
                      </a>
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
                  <div className="flex items-center gap-1.5 whitespace-nowrap">
                    <span>{fmt(s.total_reads)}</span>
                    <SampleDeltaBadge delta={s.read_delta} />
                  </div>
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
