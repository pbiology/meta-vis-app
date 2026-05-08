import type { ReactNode } from "react";

interface NtcPanelStatusProps {
  message: string;
}

export function NtcPanelStatus({ message }: Readonly<NtcPanelStatusProps>) {
  return <p className="px-4 py-8 text-center text-xs text-gray-400">{message}</p>;
}

interface NtcTableHeaderRowProps {
  headers: string[];
}

export function NtcTableHeaderRow({ headers }: Readonly<NtcTableHeaderRowProps>) {
  return (
    <tr>
      {headers.map((h) => (
        <th
          key={h}
          className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-50 whitespace-nowrap"
        >
          {h}
        </th>
      ))}
    </tr>
  );
}

interface NtcTaxonCellsProps {
  taxonName: string;
  superkingdom: string | null | undefined;
  taxonId: number;
  kingdomTone: "gray" | "orange";
}

const KINGDOM_TONE_CLASSES: Record<NtcTaxonCellsProps["kingdomTone"], string> = {
  gray: "bg-gray-100 text-gray-600",
  orange: "bg-orange-50 text-orange-700",
};

// First three cells shared between ignore + contaminant rows: italic name,
// kingdom badge (toned per list), monospace tax id.
export function NtcTaxonCells({
  taxonName,
  superkingdom,
  taxonId,
  kingdomTone,
}: Readonly<NtcTaxonCellsProps>) {
  return (
    <>
      <td className="px-4 py-3 text-xs text-gray-700 italic">{taxonName.replace(/-/g, " ")}</td>
      <td className="px-4 py-3 text-xs">
        <span className={`px-2 py-0.5 rounded text-xs ${KINGDOM_TONE_CLASSES[kingdomTone]}`}>
          {superkingdom ?? "—"}
        </span>
      </td>
      <td className="px-4 py-3 text-xs font-mono text-gray-400">{taxonId}</td>
    </>
  );
}

interface EditPencilButtonProps {
  onClick: () => void;
}

export function EditPencilButton({ onClick }: Readonly<EditPencilButtonProps>) {
  return (
    <button
      onClick={onClick}
      className="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-gray-500 transition-all"
    >
      <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
        <path
          d="M11 2l3 3-8 8H3v-3l8-8z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}

interface NtcPanelCardProps {
  title: string;
  description: string;
  action?: ReactNode;
  children: ReactNode;
}

// Header card chrome shared by every NTC list panel. Slot in an action button
// (e.g. "+ Add taxon") via `action`, body content as children.
export function NtcPanelCard({
  title,
  description,
  action,
  children,
}: Readonly<NtcPanelCardProps>) {
  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="flex items-center px-4 py-3 border-b border-gray-50">
        <div className="flex-1">
          <h2 className="text-xs font-medium text-gray-700">{title}</h2>
          <p className="text-xs text-gray-400 mt-0.5">{description}</p>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
