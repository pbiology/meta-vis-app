import { useState } from "react";
import { useBvbrcGenomes, useBvbrcSpecialtyGenes } from "../../hooks/queries/useTaxa";
import ExternalLinkButton from "./ExternalLinkButton";
import SpecialtyGenesSubsection from "./SpecialtyGenesSubsection";
import type { GenomesData, SpecialtyData } from "./types";

interface BvbrcSectionProps {
  taxonId: number;
}

export default function BvbrcSection({ taxonId }: Readonly<BvbrcSectionProps>) {
  const [collapsed, setCollapsed] = useState(false);
  const genomesQ = useBvbrcGenomes(taxonId);
  const specialtyQ = useBvbrcSpecialtyGenes(taxonId);

  const genomes = (genomesQ.data as unknown as GenomesData | undefined) ?? null;
  const specialty = (specialtyQ.data as unknown as SpecialtyData | undefined) ?? null;
  const hasGenomeData = Boolean(genomes && genomes.total_genomes > 0);

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center gap-2 px-4 py-3 border-b border-gray-100 hover:bg-gray-50 transition-colors"
      >
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1 text-left">
          BV-BRC resources
        </p>
        <svg
          className={`w-3.5 h-3.5 text-gray-300 transition-transform ${collapsed ? "-rotate-90" : ""}`}
          viewBox="0 0 16 16"
          fill="none"
        >
          <path
            d="M4 6l4 4 4-4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {!collapsed && (
        <div className="divide-y divide-gray-50">
          <div className="px-4 py-3">
            <p className="text-xs font-medium text-gray-500 mb-2">Sequenced genomes</p>
            {genomesQ.isLoading && <p className="text-xs text-gray-400">Loading…</p>}
            {!genomesQ.isLoading && (!hasGenomeData || !genomes) && (
              <p className="text-xs text-gray-300 italic">No genome data found in BV-BRC.</p>
            )}
            {!genomesQ.isLoading && hasGenomeData && genomes && (
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold text-gray-800 tabular-nums">
                    {genomes.total_genomes.toLocaleString()}
                  </span>
                  <span className="text-xs text-gray-400">genomes in BV-BRC</span>
                  <ExternalLinkButton href={genomes.bvbrc_url}>View all</ExternalLinkButton>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {genomes.isolation_sources.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 mb-1">Top isolation sources</p>
                      <ul className="space-y-0.5">
                        {genomes.isolation_sources.map((s) => (
                          <li key={s.source} className="flex items-baseline justify-between gap-2">
                            <span className="text-xs text-gray-600 truncate">{s.source}</span>
                            <span className="text-xs text-gray-400 tabular-nums flex-shrink-0">
                              {s.count}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {genomes.countries.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 mb-1">Top countries</p>
                      <ul className="space-y-0.5">
                        {genomes.countries.map((c) => (
                          <li key={c.country} className="flex items-baseline justify-between gap-2">
                            <span className="text-xs text-gray-600 truncate">{c.country}</span>
                            <span className="text-xs text-gray-400 tabular-nums flex-shrink-0">
                              {c.count}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {genomes.amr_phenotypes.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Resistant to (genomes count)</p>
                    <div className="flex flex-wrap gap-1.5">
                      {genomes.amr_phenotypes.map((a) => (
                        <span
                          key={a.antibiotic}
                          className="text-xs px-2 py-0.5 bg-red-50 text-red-600 rounded-full"
                          title={`${a.count} genome(s) resistant`}
                        >
                          {a.antibiotic} ({a.count})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          <SpecialtyGenesSubsection specialty={specialty} loadingSpecialty={specialtyQ.isLoading} />
        </div>
      )}
    </section>
  );
}
