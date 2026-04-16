const KINGDOM_BADGE = {
  Bacteria: { bg: "bg-blue-50", text: "text-blue-700" },
  Viruses: { bg: "bg-red-50", text: "text-red-700" },
  Eukaryota: { bg: "bg-amber-50", text: "text-amber-700" },
  Archaea: { bg: "bg-purple-50", text: "text-purple-700" },
};

export default function KingdomBadge({ kingdom }) {
  const style = KINGDOM_BADGE[kingdom];
  if (!style)
    return (
      <span className="inline-block text-xs px-1.5 py-0.5 rounded bg-gray-50 text-gray-400">
        {kingdom ?? "Unknown"}
      </span>
    );
  return (
    <span className={`inline-block text-xs px-1.5 py-0.5 rounded ${style.bg} ${style.text}`}>
      {kingdom}
    </span>
  );
}
