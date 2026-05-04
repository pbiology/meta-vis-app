import { TONE } from "./palette";

export type SignalKind = "pathogen" | "outbreak" | "ntc";

interface SignalPillProps {
  kind: SignalKind;
  big?: boolean;
}

const SIGNALS: Record<SignalKind, { label: string; tone: keyof typeof TONE }> = {
  pathogen: { label: "Pathogen detected", tone: "danger" },
  outbreak: { label: "Outbreak cluster", tone: "info" },
  ntc: { label: "NTC contamination", tone: "alert" },
};

export default function SignalPill({ kind, big = false }: SignalPillProps) {
  const { label, tone } = SIGNALS[kind];
  const t = TONE[tone];
  const sizing = big ? "px-2.5 py-1 text-xs rounded-md" : "px-2 py-0.5 text-[11px] rounded";
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-semibold border ${t.bg} ${t.fg} ${t.border} ${sizing}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${t.dot}`} />
      {label}
    </span>
  );
}

interface SignalDotProps {
  kind: SignalKind;
  title?: string;
}

export function SignalDot({ kind, title }: SignalDotProps) {
  const t = TONE[SIGNALS[kind].tone];
  return (
    <span
      title={title ?? SIGNALS[kind].label}
      className={`inline-block w-1.5 h-1.5 rounded-full ${t.dot}`}
    />
  );
}
