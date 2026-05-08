export default function RefreshWarning() {
  return (
    <div className="flex items-start gap-2.5 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-700">
      <svg className="w-4 h-4 flex-shrink-0 mt-0.5" viewBox="0 0 16 16" fill="none">
        <path
          d="M8 2L14 13H2L8 2z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinejoin="round"
        />
        <path d="M8 6v3M8 11v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
      <span>
        Full taxonomy data for this taxon has not been loaded yet. Run{" "}
        <code className="font-mono bg-amber-100 px-1 rounded">load_taxonomy.py</code> to populate
        lineage and rank information.
      </span>
    </div>
  );
}
