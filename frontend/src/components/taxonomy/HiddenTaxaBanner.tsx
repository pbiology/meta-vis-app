interface HiddenTaxaBannerProps {
  hiddenCount: number;
  protectedCount: number;
  listNames: string[];
  isError: boolean;
  paused: boolean;
  onShowAll: () => void;
  onReapply: () => void;
}

/**
 * States what the display filters are doing to the table. Hidden taxa must
 * never go unmentioned: a clinician reading the table has to know it is
 * incomplete, and by how much.
 */
export default function HiddenTaxaBanner({
  hiddenCount,
  protectedCount,
  listNames,
  isError,
  paused,
  onShowAll,
  onReapply,
}: Readonly<HiddenTaxaBannerProps>) {
  if (listNames.length === 0 && !isError) return null;

  if (isError) {
    return (
      <p role="alert" className="text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2">
        Display filters could not be loaded — showing all taxa.
      </p>
    );
  }

  if (paused) {
    return (
      <p className="text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="flex-1">Display filters paused — showing all taxa.</span>
        <button onClick={onReapply} className="text-blue-600 hover:text-blue-800">
          Re-apply
        </button>
      </p>
    );
  }

  if (hiddenCount === 0 && protectedCount === 0) return null;

  return (
    <p
      role="status"
      className="text-xs text-blue-800 bg-blue-50 rounded-lg px-3 py-2 flex items-center gap-2"
    >
      <span className="flex-1">
        {hiddenCount} {hiddenCount === 1 ? "taxon" : "taxa"} hidden by {listNames.join(", ")}.
        {protectedCount > 0 &&
          ` ${protectedCount} known ${
            protectedCount === 1 ? "pathogen" : "pathogens"
          } on these lists kept visible.`}
      </span>
      {hiddenCount > 0 && (
        <button onClick={onShowAll} className="text-blue-600 hover:text-blue-800">
          Show all
        </button>
      )}
    </p>
  );
}
