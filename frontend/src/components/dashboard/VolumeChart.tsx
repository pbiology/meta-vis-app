import type { VolumePoint } from "./mockData";

interface VolumeChartProps {
  data: VolumePoint[];
  height?: number;
}

// Stacked bar chart: total bars in light gray with the pathogen portion overlaid in red.
// CSS-only — no chart library — to keep the bundle small for a v1 dashboard widget.
export default function VolumeChart({ data, height = 90 }: VolumeChartProps) {
  const max = Math.max(1, ...data.map((v) => v.total));
  return (
    <div className="flex items-end gap-1 px-0.5" style={{ height }}>
      {data.map((v, i) => {
        const total = (v.total / max) * height;
        const pathogen = (v.pathogen / max) * height;
        const routine = total - pathogen;
        return (
          <div
            key={i}
            className="flex flex-col-reverse flex-1"
            style={{ height }}
            title={`${v.day} · ${v.total} cases · ${v.pathogen} pathogen`}
          >
            <div
              className="bg-gray-200"
              style={{ height: routine, borderRadius: pathogen ? 0 : "2px 2px 0 0" }}
            />
            <div className="bg-red-600" style={{ height: pathogen, borderRadius: "2px 2px 0 0" }} />
          </div>
        );
      })}
    </div>
  );
}
