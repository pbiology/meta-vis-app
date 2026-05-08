import { useCallback, useMemo, useRef, useState, type MutableRefObject } from "react";
import { scaleTime } from "@visx/scale";

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

// Builds a time scale spanning the dates in `points` (each carrying `order_date`),
// padded by ±1 day so the first/last points don't sit on the axis edge. Falls back
// to a 1-day window around `now` when there are no points.
export function useDateScale(points: ReadonlyArray<{ order_date: string }>, innerWidth: number) {
  return useMemo(() => {
    const dates = points.map((d) => new Date(d.order_date).getTime());
    const minDate = dates.length ? Math.min(...dates) : Date.now() - 86400000;
    const maxDate = dates.length ? Math.max(...dates) : Date.now();
    return scaleTime({
      domain: [new Date(minDate - 86400000), new Date(maxDate + 86400000)],
      range: [0, innerWidth],
      nice: true,
    });
  }, [points, innerWidth]);
}

export interface PointerTooltipState<T> {
  x: number;
  y: number;
  data: T;
}

// Tracks pointer-driven tooltip state for a chart. Returns the SVG ref to attach,
// a position-tracking move handler, and a clear function for `onMouseLeave`.
export function usePointerTooltip<T>(): {
  tooltip: PointerTooltipState<T> | null;
  svgRef: MutableRefObject<SVGSVGElement | null>;
  onPointerMove: (e: React.MouseEvent, data: T) => void;
  clear: () => void;
} {
  const [tooltip, setTooltip] = useState<PointerTooltipState<T> | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const onPointerMove = useCallback((e: React.MouseEvent, data: T) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, data });
  }, []);

  const clear = useCallback(() => setTooltip(null), []);

  return { tooltip, svgRef, onPointerMove, clear };
}
