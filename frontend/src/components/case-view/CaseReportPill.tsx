interface CaseReportPillProps {
  count: number;
  onClick: () => void;
}

export default function CaseReportPill({ count, onClick }: Readonly<CaseReportPillProps>) {
  const empty = count === 0;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Open report (${count} ${count === 1 ? "taxon" : "taxa"} selected)`}
      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border transition-colors ${
        empty
          ? "border-gray-200 bg-white text-gray-500 hover:bg-gray-50"
          : "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"
      }`}
    >
      <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path
          d="M4 2h6l2 2v10H4V2z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path d="M5 7h6M5 10h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
      <span>Report</span>
      <span
        className={`font-mono text-[11px] px-1.5 rounded ${
          empty ? "bg-gray-100 text-gray-500" : "bg-blue-600 text-white"
        }`}
      >
        {count}
      </span>
    </button>
  );
}
