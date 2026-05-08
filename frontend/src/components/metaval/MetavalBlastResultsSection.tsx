import { useState } from "react";
import type { BlastHitRow, BlastResults } from "./types";

interface BlastTableProps {
  rows: BlastHitRow[];
  program: string;
  onSelectTaxon: (id: string) => void;
}

const COLUMNS: { key: keyof BlastHitRow; label: string }[] = [
  { key: "qseqid", label: "Query" },
  { key: "ssciname", label: "Match" },
  { key: "staxid", label: "Tax ID" },
  { key: "median_pident", label: "% identity" },
  { key: "median_length", label: "Length" },
  { key: "median_bitscore", label: "Bitscore" },
  { key: "count", label: "Hits" },
];

function BlastTable({ rows, program, onSelectTaxon }: Readonly<BlastTableProps>) {
  const [open, setOpen] = useState(true);
  const [displayCount, setDisplayCount] = useState(10);
  const sortedData = [...rows].sort(
    (a, b) =>
      Number.parseFloat(String(b.median_bitscore ?? 0)) -
      Number.parseFloat(String(a.median_bitscore ?? 0))
  );
  const displayedRows = sortedData.slice(0, displayCount);
  const hasMore = displayCount < sortedData.length;

  return (
    <div className="border-t border-gray-50 first:border-t-0">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-2.5 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <span className="text-xs font-medium text-gray-500">{program}</span>
        <div className="flex items-center gap-2">
          {rows.length > 0 && (
            <span className="text-xs text-gray-400">
              {rows.length} {rows.length === 1 ? "hit" : "hits"}
            </span>
          )}
          <svg
            className={`w-3 h-3 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
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
        </div>
      </button>
      {open && rows.length === 0 && <p className="px-5 py-4 text-xs text-gray-300">No hits</p>}
      {open && rows.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr>
                  {COLUMNS.map((c) => (
                    <th
                      key={String(c.key)}
                      className="px-5 py-2 text-xs font-medium text-gray-400 border-b border-gray-100 whitespace-nowrap"
                    >
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {displayedRows.map((row, i) => (
                  <tr
                    key={`${row.qseqid ?? i}-${row.staxid ?? ""}`}
                    className="border-t border-gray-50 hover:bg-gray-50"
                  >
                    <td
                      className="px-5 py-2 text-xs font-mono text-gray-600 max-w-48 truncate"
                      title={row.qseqid}
                    >
                      {row.qseqid}
                    </td>
                    <td className="px-5 py-2 text-xs italic text-gray-700">
                      {row.staxid ? (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectTaxon(String(row.staxid));
                          }}
                          className="underline text-gray-700 hover:text-gray-900 text-left"
                        >
                          {row.ssciname}
                        </button>
                      ) : (
                        row.ssciname
                      )}
                    </td>
                    <td className="px-5 py-2 text-xs font-mono text-gray-400">{row.staxid}</td>
                    <td className="px-5 py-2 text-xs text-gray-500 tabular-nums">
                      {row.median_pident}
                    </td>
                    <td className="px-5 py-2 text-xs text-gray-500 tabular-nums">
                      {row.median_length}
                    </td>
                    <td className="px-5 py-2 text-xs text-gray-500 tabular-nums">
                      {row.median_bitscore}
                    </td>
                    <td className="px-5 py-2 text-xs text-gray-500 tabular-nums">{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <div className="px-5 py-3 border-t border-gray-50">
              <button
                onClick={() => setDisplayCount((prev) => prev + 10)}
                className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
              >
                Load more ({sortedData.length - displayCount} remaining)
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

interface MetavalBlastResultsSectionProps {
  blast: BlastResults | undefined;
  onSelectTaxon: (id: string) => void;
}

export default function MetavalBlastResultsSection({
  blast,
  onSelectTaxon,
}: Readonly<MetavalBlastResultsSectionProps>) {
  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="px-5 py-3.5 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">BLAST results</p>
      </div>
      <BlastTable rows={blast?.blastn ?? []} program="BLASTn" onSelectTaxon={onSelectTaxon} />
      <BlastTable rows={blast?.blastx ?? []} program="BLASTx" onSelectTaxon={onSelectTaxon} />
    </section>
  );
}
