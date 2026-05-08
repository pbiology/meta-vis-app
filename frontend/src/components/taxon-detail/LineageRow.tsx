interface LineageRowProps {
  label: string;
  value?: string | null;
}

export default function LineageRow({ label, value }: Readonly<LineageRowProps>) {
  if (!value) return null;
  return (
    <div className="flex items-baseline gap-2 py-1 border-b border-gray-50 last:border-0">
      <span className="text-xs text-gray-400 w-24 flex-shrink-0">{label}</span>
      <span className="text-xs text-gray-700 italic">{value}</span>
    </div>
  );
}
