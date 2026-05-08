import { useMemo } from "react";
import { scaleLinear } from "@visx/scale";
import { Group } from "@visx/group";
import type { NtcKingdomPoint } from "../../api/types";
import {
  CHART_MARGIN,
  KINGDOMS,
  KINGDOM_COLOURS,
  useDateScale,
  usePointerTooltip,
} from "./chartUtils";
import ChartAxes from "./ChartAxes";

interface KingdomBreakdownChartProps {
  data: NtcKingdomPoint[];
  width?: number;
  height?: number;
}

export default function KingdomBreakdownChart({
  data,
  width = 600,
  height = 220,
}: Readonly<KingdomBreakdownChartProps>) {
  const points = data.filter((d) => d.order_date);
  const innerWidth = width - CHART_MARGIN.left - CHART_MARGIN.right;
  const innerHeight = height - CHART_MARGIN.top - CHART_MARGIN.bottom;

  const xScale = useDateScale(points, innerWidth);

  const yScale = useMemo(() => {
    const maxTotal = points.length
      ? Math.max(...points.map((d) => KINGDOMS.reduce((s, k) => s + (d[k] ?? 0), 0)))
      : 10;
    return scaleLinear({
      domain: [0, maxTotal * 1.1 || 10],
      range: [innerHeight, 0],
      nice: true,
    });
  }, [points, innerHeight]);

  const BAR_HALF = Math.max(2, Math.min(8, innerWidth / (points.length * 4)));

  const { tooltip, svgRef, onPointerMove, clear } = usePointerTooltip<NtcKingdomPoint>();

  if (points.length === 0) {
    return (
      <p className="text-xs text-gray-400 text-center py-8">No kingdom data in this window.</p>
    );
  }

  return (
    <div className="relative">
      <svg ref={svgRef} width={width} height={height} onMouseLeave={clear}>
        <Group left={CHART_MARGIN.left} top={CHART_MARGIN.top}>
          <ChartAxes
            xScale={xScale}
            yScale={yScale}
            innerWidth={innerWidth}
            innerHeight={innerHeight}
          />
          {points.map((d) => {
            const x = xScale(new Date(d.order_date));
            let yOffset = innerHeight;
            return (
              <g key={`${d.sample_id}-${d.order_date}`} onMouseMove={(e) => onPointerMove(e, d)}>
                {KINGDOMS.map((kingdom) => {
                  const val = d[kingdom] ?? 0;
                  if (val === 0) return null;
                  const barHeight = innerHeight - yScale(val);
                  yOffset -= barHeight;
                  return (
                    <rect
                      key={kingdom}
                      x={x - BAR_HALF}
                      y={yOffset}
                      width={BAR_HALF * 2}
                      height={barHeight}
                      fill={KINGDOM_COLOURS[kingdom]}
                      fillOpacity={0.85}
                    />
                  );
                })}
              </g>
            );
          })}
        </Group>
      </svg>

      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 pl-[60px]">
        {KINGDOMS.map((k) => (
          <div key={k} className="flex items-center gap-1.5">
            <span
              className="inline-block w-2.5 h-2.5 rounded-sm"
              style={{ backgroundColor: KINGDOM_COLOURS[k] }}
            />
            <span className="text-xs text-gray-500">{k}</span>
          </div>
        ))}
      </div>

      {tooltip && (
        <div
          className="absolute pointer-events-none bg-white border border-gray-200 rounded-lg shadow-sm px-2.5 py-1.5 text-xs font-mono text-gray-700"
          style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}
        >
          <div className="font-medium">{tooltip.data.sample_id}</div>
          <div className="text-gray-400 mb-1">{tooltip.data.order_date}</div>
          {KINGDOMS.map((k) => {
            const v = tooltip.data[k] ?? 0;
            return v > 0 ? (
              <div key={k} className="flex items-center gap-1.5">
                <span
                  className="inline-block w-2 h-2 rounded-sm flex-shrink-0"
                  style={{ backgroundColor: KINGDOM_COLOURS[k] }}
                />
                <span style={{ color: KINGDOM_COLOURS[k] }}>{k}</span>
                <span className="text-gray-400 ml-auto pl-3">{v.toLocaleString()}</span>
              </div>
            ) : null;
          })}
        </div>
      )}
    </div>
  );
}
