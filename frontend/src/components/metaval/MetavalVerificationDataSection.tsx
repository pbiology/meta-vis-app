import { useState } from "react";
import { useSubmitBlast } from "../../hooks/queries/useMetaval";
import { axiosErrorDetail } from "../../utils/axiosError";
import type { MetavalResult } from "../../api/types";
import BlastModal, { type BlastStatus } from "./BlastModal";
import type { VerificationData } from "./types";

const TYPE_LABEL: Record<string, string> = {
  scaffolds: "Scaffolds",
  contigs: "Contigs",
  raw_reads: "Raw reads",
};

interface BlastState {
  open: boolean;
  status: BlastStatus;
  error: string | null;
}

interface MetavalVerificationDataSectionProps {
  metavalId: string;
  result: MetavalResult | null;
}

function sequenceCountLabel(vd: VerificationData): string {
  if (vd.count == null) return "—";
  if (vd.type === "raw_reads") {
    const fc = vd.file_count ?? 1;
    return `${vd.count.toLocaleString()} × ${fc} (${fc > 1 ? "paired-end" : "single-end"})`;
  }
  return vd.count.toLocaleString();
}

export default function MetavalVerificationDataSection({
  metavalId,
  result,
}: Readonly<MetavalVerificationDataSectionProps>) {
  const [blastState, setBlastState] = useState<BlastState>({
    open: false,
    status: "blasting",
    error: null,
  });
  const submitBlast = useSubmitBlast();

  const vd = (result?.verification_data ?? {}) as VerificationData;
  const closeBlast = () => setBlastState((s) => ({ ...s, open: false }));

  const handleBlastClick = () => {
    setBlastState({ open: true, status: "blasting", error: null });
    submitBlast.mutate(metavalId, {
      onSuccess: (data) => {
        window.open(data.results_url, "_blank");
        closeBlast();
      },
      onError: (err: unknown) => {
        const msg = axiosErrorDetail(err, "BLAST submission failed. Please try again.");
        setBlastState({ open: true, status: "error", error: msg });
      },
    });
  };

  return (
    <>
      {blastState.open && (
        <BlastModal status={blastState.status} error={blastState.error} onClose={closeBlast} />
      )}

      <section className="bg-white border border-gray-100 rounded-xl">
        <div className="px-5 py-3.5 border-b border-gray-100">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
            Taxon verification data
          </p>
        </div>

        {vd.type ? (
          <table className="w-full text-left">
            <thead>
              <tr>
                {["Type", "Sequences", "Avg length", "Data availability", ""].map((h) => (
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
              <tr>
                <td className="px-5 py-2.5 text-xs text-gray-600">
                  {TYPE_LABEL[vd.type] ?? vd.type}
                </td>
                <td className="px-5 py-2.5 text-xs text-gray-500 tabular-nums">
                  {sequenceCountLabel(vd)}
                </td>
                <td className="px-5 py-2.5 text-xs text-gray-500 tabular-nums">
                  {vd.avg_length == null ? "—" : `${vd.avg_length} bp`}
                </td>
                <td className="px-5 py-2.5 text-xs text-gray-400">
                  {vd.available ? (
                    "Available"
                  ) : (
                    <span className="text-gray-300">Not available</span>
                  )}
                </td>
                <td className="px-5 py-2.5 text-right">
                  {vd.available && (
                    <button
                      onClick={handleBlastClick}
                      className="text-xs px-3 py-1 rounded-lg bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors"
                    >
                      BLAST
                    </button>
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        ) : (
          <p className="px-5 py-8 text-xs text-gray-300 text-center">
            No verification data was ingested for this taxon.
          </p>
        )}
      </section>
    </>
  );
}
