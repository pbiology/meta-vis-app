import { useMemo } from "react";
import { scaleLinear } from "@visx/scale";
import { Circle } from "@visx/shape";
import { Group } from "@visx/group";
import type { NtcReadCountPoint } from "../../api/types";
import { CHART_MARGIN, useDateScale, usePointerTooltip } from "./chartUtils";
import ChartAxes from "./ChartAxes";

interface ReadCountChartProps {
  data: NtcReadCountPoint[];
  width?: number;
  height?: number;
  isFraction?: boolean;
}

export default function ReadCountChart({
  data,
  width = 600,
  height = 200,
  isFraction = false,
}: Readonly<ReadCountChartProps>) {
  const points = data.filter((d) => d.order_date && d.classified_reads != null);
  const innerWidth = width - CHART_MARGIN.left - CHART_MARGIN.right;
  const innerHeight = height - CHART_MARGIN.top - CHART_MARGIN.bottom;

  const xScale = useDateScale(points, innerWidth);

  const yScale = useMemo(() => {
    const maxVal = points.length ? Math.max(...points.map((d) => d.classified_reads)) : 100;
    return scaleLinear({
      domain: [0, maxVal * 1.1 || 100],
      range: [innerHeight, 0],
      nice: true,
    });
  }, [points, innerHeight]);

  const { tooltip, svgRef, onPointerMove, clear } = usePointerTooltip<NtcReadCountPoint>();

  if (points.length === 0) {
    return (
      <p className="text-xs text-gray-400 text-center py-8">No read count data in this window.</p>
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
          <line
            x1={0}
            x2={innerWidth}
            y1={yScale(1000)}
            y2={yScale(1000)}
            stroke="#fca5a5"
            strokeWidth={1}
            strokeDasharray="4,4"
          />
          <text
            x={innerWidth - 4}
            y={yScale(1000) - 4}
            textAnchor="end"
            fontSize={9}
            fill="#f87171"
            fontFamily="DM Mono, monospace"
          >
            1000
          </text>
          {points.map((d) => (
            <Circle
              key={`${d.sample_id}-${d.order_date}`}
              cx={xScale(new Date(d.order_date))}
              cy={yScale(d.classified_reads)}
              r={4}
              fill="#3b82f6"
              fillOpacity={0.7}
              style={{ cursor: "pointer" }}
              onMouseMove={(e) => onPointerMove(e, d)}
            />
          ))}
        </Group>
      </svg>
      {tooltip && (
        <div
          className="absolute pointer-events-none bg-white border border-gray-200 rounded-lg shadow-sm px-2.5 py-1.5 text-xs font-mono text-gray-700"
          style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}
        >
          <div className="font-medium">{tooltip.data.sample_id}</div>
          <div className="text-gray-400">{tooltip.data.case_id}</div>
          <div>
            {tooltip.data.classified_reads.toLocaleString()}{" "}
            {isFraction ? "processed reads" : "classified reads"}
          </div>
          <div className="text-gray-400">{tooltip.data.order_date}</div>
        </div>
      )}
    </div>
  );
}
