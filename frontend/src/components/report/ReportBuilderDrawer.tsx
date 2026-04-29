import { useReportBuilder } from "../../context/ReportBuilderContext";

export interface DrawerTaxonInfo {
  taxon_id: number;
  name: string;
  rank?: string;
}

interface ReportBuilderDrawerProps {
  sampleId: string;
  taxonLookup: Map<number, DrawerTaxonInfo>;
}

export default function ReportBuilderDrawer({
  sampleId,
  taxonLookup,
}: Readonly<ReportBuilderDrawerProps>) {
  const { selectedFor, removeTaxon, clear } = useReportBuilder();
  const ids = selectedFor(sampleId);

  if (ids.length === 0) return null;

  return (
    <aside
      aria-label="Report builder"
      className="fixed top-0 right-0 z-30 h-screen w-[340px] bg-white border-l border-gray-200 shadow-lg flex flex-col"
    >
      <header className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-400">Report</p>
          <p className="text-sm font-medium text-gray-700">
            {ids.length} {ids.length === 1 ? "taxon" : "taxa"} selected
          </p>
        </div>
        <button
          type="button"
          onClick={() => clear(sampleId)}
          className="text-xs text-gray-500 hover:text-red-600 transition-colors"
        >
          Clear all
        </button>
      </header>

      <ul className="flex-1 overflow-y-auto divide-y divide-gray-50">
        {ids.map((id) => {
          const info = taxonLookup.get(id);
          return (
            <li key={id} className="px-4 py-2 flex items-center gap-2">
              <div className="flex-1 min-w-0">
                <p className="text-xs italic text-gray-700 truncate">
                  {info?.name ?? `Taxon ${id}`}
                </p>
                {info?.rank && <p className="text-[11px] text-gray-400">{info.rank}</p>}
              </div>
              <button
                type="button"
                aria-label={`Remove ${info?.name ?? id} from report`}
                onClick={() => removeTaxon(sampleId, id)}
                className="text-gray-400 hover:text-red-600 text-base leading-none px-1"
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>

      <footer className="px-4 py-3 border-t border-gray-100">
        <button
          type="button"
          disabled
          title="Available in the next phase"
          className="w-full text-xs px-3 py-1.5 rounded-lg bg-gray-100 text-gray-400 cursor-not-allowed"
        >
          Preview report
        </button>
      </footer>
    </aside>
  );
}
