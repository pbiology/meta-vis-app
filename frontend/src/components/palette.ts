// Semantic palette tokens shared by the dashboard and case-view redesigns.
// Maps the design canvas's PALETTE constants to Tailwind utility class strings
// so the redesign uses the same fg/bg/border/dot color set everywhere.

export type Tone = "ok" | "warn" | "danger" | "alert" | "info";

export interface ToneClasses {
  fg: string;
  bg: string;
  border: string;
  dot: string;
}

export const TONE: Record<Tone, ToneClasses> = {
  ok: {
    fg: "text-green-700",
    bg: "bg-green-50",
    border: "border-green-200",
    dot: "bg-green-600",
  },
  warn: {
    fg: "text-amber-700",
    bg: "bg-amber-50",
    border: "border-amber-200",
    dot: "bg-amber-600",
  },
  danger: {
    fg: "text-red-700",
    bg: "bg-red-50",
    border: "border-red-200",
    dot: "bg-red-600",
  },
  alert: {
    fg: "text-orange-700",
    bg: "bg-orange-50",
    border: "border-orange-200",
    dot: "bg-orange-600",
  },
  info: {
    fg: "text-blue-700",
    bg: "bg-blue-50",
    border: "border-blue-200",
    dot: "bg-blue-600",
  },
};
