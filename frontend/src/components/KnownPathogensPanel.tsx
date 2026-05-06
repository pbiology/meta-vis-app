import type { PathogenItem, Sample } from "../api/types";

interface Props {
  samples: Sample[];
  pathogenMap: Record<number, PathogenItem>;
}

interface PathogenHit {
  taxonId: number;
  pathogen: PathogenItem;
  samples: Sample[];
}

export default function KnownPathogensPanel({ samples, pathogenMap }: Readonly<Props>) {
  const byTaxon = new Map<number, PathogenHit>();
  for (const s of samples) {
    const ids = (s.all_taxon_ids as number[] | undefined) ?? [];
    for (const id of ids) {
      const p = pathogenMap[id];
      if (!p) continue;
      let hit = byTaxon.get(id);
      if (!hit) {
        hit = { taxonId: id, pathogen: p, samples: [] };
        byTaxon.set(id, hit);
      }
      hit.samples.push(s);
    }
  }
  const hits = Array.from(byTaxon.values()).sort((a, b) => b.samples.length - a.samples.length);

  return (
    <section className="bg-white border border-gray-100 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900 m-0">
          Known pathogens detected
        </h3>
      </div>
      {hits.length === 0 ? (
        <p className="px-4 py-6 text-center text-xs text-gray-400">
          No known pathogens detected in this case.
        </p>
      ) : (
        <table className="w-full text-left border-collapse">
          <thead>
            <tr>
              {["Taxon", "Kingdom", "Notes", "Detected in"].map((h) => (
                <th
                  key={h}
                  className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100 whitespace-nowrap"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {hits.map((hit) => (
              <tr key={hit.taxonId} className="border-b border-gray-50">
                <td className="px-4 py-3 text-xs">
                  <a
                    href={`/taxa/${hit.taxonId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="italic text-gray-900 hover:underline"
                  >
                    {hit.pathogen.taxon_name.replace(/-/g, " ")}
                  </a>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  <span className="bg-red-50 text-red-700 px-2 py-0.5 rounded text-xs font-medium">
                    {hit.pathogen.superkingdom}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500 min-w-40">
                  {hit.pathogen.reason ?? <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1.5">
                    {hit.samples.slice(0, 4).map((s) => (
                      <a
                        key={s._id as string}
                        href={`/samples/${s._id}/taxa/${hit.taxonId}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-[11px] px-1.5 py-0.5 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                      >
                        {s.sample_id}
                      </a>
                    ))}
                    {hit.samples.length > 4 && (
                      <span className="text-[11px] text-gray-400">
                        +{hit.samples.length - 4} more
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
