import { TONE, type Tone } from "../palette";

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  tone?: Tone;
  accent?: boolean;
}

export default function StatCard({ label, value, sub, tone, accent }: StatCardProps) {
  const t = tone ? TONE[tone] : null;
  return (
    <div className="relative overflow-hidden bg-white border border-gray-100 rounded-lg p-4 flex flex-col gap-1">
      {accent && t && <div className={`absolute left-0 top-0 bottom-0 w-[3px] ${t.dot}`} />}
      <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
        {label}
      </span>
      <span
        className={`text-2xl font-semibold leading-tight tracking-tight ${t?.fg ?? "text-gray-900"}`}
      >
        {value}
      </span>
      {sub && <span className="text-[11px] text-gray-500">{sub}</span>}
    </div>
  );
}
