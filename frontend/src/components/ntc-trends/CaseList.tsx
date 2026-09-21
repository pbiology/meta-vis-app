interface CaseListProps {
  caseIds?: string[];
}

// Beyond this the tooltip stops being readable; the count still tells the
// reader how many cases the control covers.
const MAX_SHOWN = 3;

/**
 * The cases a control was sequenced alongside.
 *
 * One physical NTC is run with every case in its batch, so a single point on
 * the trend charts routinely belongs to several cases. Showing the count keeps
 * that visible instead of implying the control belongs to just one.
 */
export default function CaseList({ caseIds }: Readonly<CaseListProps>) {
  if (!caseIds || caseIds.length === 0) return null;

  if (caseIds.length === 1) {
    return <div className="text-gray-400">{caseIds[0]}</div>;
  }

  const shown = caseIds.slice(0, MAX_SHOWN);
  const hidden = caseIds.length - shown.length;

  return (
    <div className="text-gray-400">
      {caseIds.length} cases: {shown.join(", ")}
      {hidden > 0 ? ` +${hidden}` : ""}
    </div>
  );
}
