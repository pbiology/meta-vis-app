import { useEffect, useState } from "react";
import { useIgvUrl } from "../../hooks/queries/useMetaval";
import type { CandidateOrganism } from "./types";

interface MetavalCandidateOrganismsSectionProps {
  metavalId: string;
  organisms: CandidateOrganism[] | undefined;
}

export default function MetavalCandidateOrganismsSection({
  metavalId,
  organisms,
}: Readonly<MetavalCandidateOrganismsSectionProps>) {
  const [selected, setSelected] = useState<CandidateOrganism | null>(null);
  const tooLarge = selected?.igv_too_large ?? false;
  const igvQ = useIgvUrl(metavalId, selected?.organism_name ?? "", {
    enabled: Boolean(selected) && !tooLarge,
  });

  // Revoke the blob URL when it changes or on unmount.
  useEffect(() => {
    if (!igvQ.data) return;
    return () => URL.revokeObjectURL(igvQ.data);
  }, [igvQ.data]);

  if (!organisms || organisms.length === 0) {
    return (
      <section className="bg-white border border-gray-100 rounded-xl">
        <div className="px-5 py-3.5 border-b border-gray-100">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
            Candidate organisms
          </p>
        </div>
        <p className="px-5 py-8 text-xs text-gray-300 text-center">No predicted candidate found</p>
      </section>
    );
  }

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="px-5 py-3.5 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
          Candidate organisms
        </p>
      </div>
      <table className="w-full text-left">
        <thead>
          <tr>
            {["Organism", "IGV size", ""].map((h) => (
              <th
                key={h}
                className="px-5 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {organisms.map((org) => (
            <tr
              key={org.organism_name}
              onClick={() => setSelected(org)}
              className={`cursor-pointer border-t border-gray-50 transition-colors ${
                selected?.organism_name === org.organism_name ? "bg-blue-50" : "hover:bg-gray-50"
              }`}
            >
              <td className="px-5 py-2.5 text-xs italic text-gray-700">
                {org.organism_name.replace(/-/g, " ")}
              </td>
              <td className="px-5 py-2.5 text-xs text-gray-400 tabular-nums">
                {org.igv_too_large ? (
                  <span className="text-red-400">&gt; 10 MB</span>
                ) : (
                  `${((org.igv_file_size_bytes ?? 0) / 1024).toFixed(0)} KB`
                )}
              </td>
              <td className="px-5 py-2.5 text-right">
                {selected?.organism_name === org.organism_name && (
                  <span className="text-xs text-blue-500">viewing</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected && (
        <div className="border-t border-gray-100 p-5">
          {tooLarge && (
            <p className="text-xs text-red-400">IGV file exceeds 10 MB and cannot be displayed.</p>
          )}
          {!tooLarge && igvQ.isError && (
            <p className="text-xs text-red-400">Failed to load IGV report.</p>
          )}
          {!tooLarge && igvQ.isLoading && (
            <div className="flex items-center justify-center h-40 text-sm text-gray-400">
              Loading IGV…
            </div>
          )}
          {!tooLarge && igvQ.data && !igvQ.isLoading && (
            <iframe
              src={igvQ.data}
              title="IGV report"
              className="w-full rounded-lg border border-gray-100"
              style={{ height: "75vh" }}
              sandbox="allow-scripts allow-popups allow-forms"
            />
          )}
        </div>
      )}
    </section>
  );
}
