import { useState } from "react";
import ExternalLinkButton from "./ExternalLinkButton";
import PubmedLinks from "./PubmedLinks";
import type { SpecialtyData } from "./types";

interface SpecialtyHeaderSummaryProps {
  loadingSpecialty: boolean;
  hasSpecialtyData: boolean;
  amrCount: number;
  vfCount: number;
}

function SpecialtyHeaderSummary({
  loadingSpecialty,
  hasSpecialtyData,
  amrCount,
  vfCount,
}: Readonly<SpecialtyHeaderSummaryProps>) {
  if (loadingSpecialty) return null;
  if (!hasSpecialtyData)
    return <span className="text-xs text-gray-300 italic">No data in BV-BRC</span>;
  return (
    <div className="flex items-center gap-2">
      {amrCount > 0 && (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600">
          <svg className="w-3 h-3 flex-shrink-0" viewBox="0 0 16 16" fill="none">
            <path
              d="M8 1.5L2 4v4c0 3.3 2.5 5.8 6 7 3.5-1.2 6-3.7 6-7V4L8 1.5z"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinejoin="round"
            />
            <path
              d="M5.5 8l1.8 1.8L10.5 6"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          {amrCount} AMR {amrCount === 1 ? "gene" : "genes"}
        </span>
      )}
      {vfCount > 0 && (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-600">
          <svg className="w-3 h-3 flex-shrink-0" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="1.5" stroke="currentColor" strokeWidth="1.4" />
            <path
              d="M8 6.5C8 4.6 6.4 3 4.5 3S1 4.6 1 6.5c0 1.4.8 2.6 2 3.2M8 6.5C8 4.6 9.6 3 11.5 3S15 4.6 15 6.5c0 1.4-.8 2.6-2 3.2M5 12.5c.9.5 1.9.8 3 .8s2.1-.3 3-.8"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
            />
          </svg>
          {vfCount} virulence {vfCount === 1 ? "factor" : "factors"}
        </span>
      )}
    </div>
  );
}

interface SpecialtyGenesSubsectionProps {
  specialty: SpecialtyData | null;
  loadingSpecialty: boolean;
}

export default function SpecialtyGenesSubsection({
  specialty,
  loadingSpecialty,
}: Readonly<SpecialtyGenesSubsectionProps>) {
  const [collapsed, setCollapsed] = useState(true);

  const hasSpecialtyData = Boolean(
    specialty &&
    (specialty.amr_genes.length > 0 ||
      specialty.virulence_factors.length > 0 ||
      specialty.amr_phenotypes.length > 0)
  );

  const amrCount = specialty?.amr_genes?.length ?? 0;
  const vfCount = specialty?.virulence_factors?.length ?? 0;

  return (
    <div className="border-t border-gray-50">
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center gap-2 px-4 py-3 hover:bg-gray-50 transition-colors"
      >
        <p className="text-xs font-medium text-gray-500 flex-shrink-0">Specialty genes</p>
        <div className="flex-1 flex justify-start">
          <SpecialtyHeaderSummary
            loadingSpecialty={loadingSpecialty}
            hasSpecialtyData={hasSpecialtyData}
            amrCount={amrCount}
            vfCount={vfCount}
          />
        </div>
        <svg
          className={`w-3 h-3 text-gray-300 flex-shrink-0 transition-transform ${collapsed ? "-rotate-90" : ""}`}
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

      {!collapsed && hasSpecialtyData && specialty && !loadingSpecialty && (
        <div className="px-4 pb-3">
          <div className="flex flex-col gap-4">
            {specialty.amr_genes.length > 0 && (
              <div>
                <p className="text-xs text-gray-400 mb-1">
                  AMR genes ({specialty.amr_genes.length})
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr>
                        {["Gene", "Antibiotics", "Class", "Source", "PubMed"].map((h) => (
                          <th
                            key={h}
                            className="px-3 py-1.5 text-xs font-medium text-gray-400 border-b border-gray-100"
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {specialty.amr_genes.map((g, i) => (
                        <tr key={g.gene ?? i} className="border-t border-gray-50 hover:bg-gray-50">
                          <td className="px-3 py-1.5 text-xs font-mono text-gray-700">
                            {g.gene || "—"}
                          </td>
                          <td className="px-3 py-1.5 text-xs text-gray-500">
                            {g.antibiotics && g.antibiotics.length > 0
                              ? g.antibiotics.join(", ")
                              : "—"}
                          </td>
                          <td className="px-3 py-1.5 text-xs text-gray-500">
                            {g.antibiotics_class || "—"}
                          </td>
                          <td className="px-3 py-1.5 text-xs text-gray-400">{g.source || "—"}</td>
                          <td className="px-3 py-1.5">
                            <PubmedLinks pmids={g.pmid} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {specialty.virulence_factors.length > 0 && (
              <div>
                <p className="text-xs text-gray-400 mb-1">
                  Virulence factors ({specialty.virulence_factors.length})
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr>
                        {["Gene", "Product", "Source", "PubMed"].map((h) => (
                          <th
                            key={h}
                            className="px-3 py-1.5 text-xs font-medium text-gray-400 border-b border-gray-100"
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {specialty.virulence_factors.map((g, i) => (
                        <tr key={g.gene ?? i} className="border-t border-gray-50 hover:bg-gray-50">
                          <td className="px-3 py-1.5 text-xs font-mono text-gray-700">
                            {g.gene || "—"}
                          </td>
                          <td className="px-3 py-1.5 text-xs text-gray-500">{g.product || "—"}</td>
                          <td className="px-3 py-1.5 text-xs text-gray-400">{g.source || "—"}</td>
                          <td className="px-3 py-1.5">
                            <PubmedLinks pmids={g.pmid} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {specialty.amr_phenotypes.length > 0 && (
              <div>
                <p className="text-xs text-gray-400 mb-1">
                  AMR phenotypes ({specialty.amr_phenotypes.length} antibiotics)
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr>
                        {["Antibiotic", "Resistant", "Susceptible"].map((h) => (
                          <th
                            key={h}
                            className="px-3 py-1.5 text-xs font-medium text-gray-400 border-b border-gray-100"
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {specialty.amr_phenotypes.map((p) => (
                        <tr key={p.antibiotic} className="border-t border-gray-50 hover:bg-gray-50">
                          <td className="px-3 py-1.5 text-xs text-gray-700">{p.antibiotic}</td>
                          <td className="px-3 py-1.5 text-xs tabular-nums text-red-600">
                            {p.resistant}
                          </td>
                          <td className="px-3 py-1.5 text-xs tabular-nums text-green-600">
                            {p.susceptible}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {specialty.bvbrc_url && (
              <div>
                <ExternalLinkButton href={specialty.bvbrc_url}>View in BV-BRC</ExternalLinkButton>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
