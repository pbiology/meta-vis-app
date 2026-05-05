import type { PathogenItem, Sample } from "../../../api/types";

interface CaseTaxaProps {
  samples: Sample[];
  pathogenMap: Record<number, PathogenItem>;
}

interface TaxonHit {
  taxonId: number;
  pathogen: PathogenItem;
  samples: Sample[];
}

// Aggregates pathogen-flagged taxa across the case's samples. Read-only summary
// — no API of its own; derived from the same `all_taxon_ids` field that the
// Samples table uses to render inline pathogen pills.
export default function CaseTaxa({ samples, pathogenMap }: Readonly<CaseTaxaProps>) {
  const byTaxon = new Map<number, TaxonHit>();
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
          Taxa of interest · {hits.length}
        </h3>
      </div>
      {hits.length === 0 ? (
        <div className="px-4 py-8 text-center text-xs text-gray-400">
          No flagged taxa detected in this case&apos;s samples.
        </div>
      ) : (
        <ul className="divide-y divide-gray-50">
          {hits.map((h) => (
            <li key={h.taxonId} className="px-4 py-3 flex items-start gap-3">
              <a
                href={`/taxa/${h.taxonId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 min-w-0 text-sm italic text-gray-900 hover:underline truncate"
              >
                {h.pathogen.taxon_name}
              </a>
              <span className="text-[11px] text-gray-500">
                {h.samples.length} sample{h.samples.length === 1 ? "" : "s"}
              </span>
              <div className="flex flex-wrap gap-1.5 max-w-[40%]">
                {h.samples.slice(0, 4).map((s) => (
                  <a
                    key={s._id as string}
                    href={`/samples/${s._id}/taxa/${h.taxonId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono text-[11px] px-1.5 py-0.5 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                  >
                    {s.sample_id}
                  </a>
                ))}
                {h.samples.length > 4 && (
                  <span className="text-[11px] text-gray-400">+{h.samples.length - 4} more</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
