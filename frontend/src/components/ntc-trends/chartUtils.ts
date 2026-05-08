import { useCallback, useRef, useState } from "react";

export const CHART_MARGIN = { top: 16, right: 24, bottom: 48, left: 72 } as const;

export const KINGDOM_COLOURS: Record<string, string> = {
  Bacteria: "#3b82f6",
  Viruses: "#ef4444",
  Eukaryota: "#10b981",
  Archaea: "#f59e0b",
  Other: "#d1d1d6",
};

export const KINGDOMS = ["Bacteria", "Viruses", "Eukaryota", "Archaea", "Other"] as const;

export const TAXON_COLOURS = [
  "#3b82f6",
  "#8b5cf6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#06b6d4",
  "#f97316",
  "#84cc16",
];

export function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toPrecision(3)}M`;
  if (n >= 1_000) return `${(n / 1_000).toPrecision(3)}k`;
  return String(n);
}

export function isoWeek(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

export function weekTicks(minDate: Date, maxDate: Date): Date[] {
  const ticks: Date[] = [];
  const d = new Date(minDate);
  d.setDate(d.getDate() + ((1 - d.getDay() + 7) % 7 || 7));
  while (d <= maxDate) {
    ticks.push(new Date(d));
    d.setDate(d.getDate() + 7);
  }
  return ticks;
}

export function useContainerWidth(): [(node: HTMLElement | null) => void, number] {
  const [width, setWidth] = useState(0);
  const observerRef = useRef<ResizeObserver | null>(null);

  const ref = useCallback((node: HTMLElement | null) => {
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
    }
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => {
      setWidth(entry.contentRect.width);
    });
    observer.observe(node);
    setWidth(node.getBoundingClientRect().width);
    observerRef.current = observer;
  }, []);

  return [ref, width];
}

// Common axis label styling — keeps tick text consistent across charts.
export const AXIS_TICK_LABEL_PROPS = {
  fontSize: 10,
  fill: "#a1a1aa",
  fontFamily: "DM Mono, monospace",
} as const;
