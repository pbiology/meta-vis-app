import type { PathogenItem, SampleProfile, SampleProfileEntry } from "../../api/types";
import DataWarning from "../DataWarning";

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

interface SampleKnownPathogensSectionProps {
  pathogenError: boolean;
  pathogenIds: Set<number>;
  classifiers: SampleProfile[];
  pathogenMap: Record<string | number, PathogenItem>;
}

export default function SampleKnownPathogensSection({
  pathogenError,
  pathogenIds,
  classifiers,
  pathogenMap,
}: Readonly<SampleKnownPathogensSectionProps>) {
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
