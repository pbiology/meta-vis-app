import { useMemo, useRef, useState } from "react";
import { scaleLinear, scaleTime } from "@visx/scale";
import { Circle } from "@visx/shape";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { GridRows } from "@visx/grid";
import { Group } from "@visx/group";
import type { NtcReadCountPoint } from "../../api/types";
import { AXIS_TICK_LABEL_PROPS, CHART_MARGIN, formatCount, isoWeek, weekTicks } from "./chartUtils";

interface ReadTooltip {
  x: number;
  y: number;
  data: NtcReadCountPoint;
}

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
  const [tooltip, setTooltip] = useState<ReadTooltip | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const points = data.filter((d) => d.order_date && d.classified_reads != null);
  const innerWidth = width - CHART_MARGIN.left - CHART_MARGIN.right;
  const innerHeight = height - CHART_MARGIN.top - CHART_MARGIN.bottom;

  const xScale = useMemo(() => {
    const dates = points.map((d) => new Date(d.order_date).getTime());
    const minDate = dates.length ? Math.min(...dates) : Date.now() - 86400000;
    const maxDate = dates.length ? Math.max(...dates) : Date.now();
    return scaleTime({
      domain: [new Date(minDate - 86400000), new Date(maxDate + 86400000)],
      range: [0, innerWidth],
      nice: true,
    });
  }, [points, innerWidth]);

  const yScale = useMemo(() => {
    const maxVal = points.length ? Math.max(...points.map((d) => d.classified_reads)) : 100;
    return scaleLinear({
      domain: [0, maxVal * 1.1 || 100],
      range: [innerHeight, 0],
      nice: true,
    });
  }, [points, innerHeight]);

  if (points.length === 0) {
    return (
      <p className="text-xs text-gray-400 text-center py-8">No read count data in this window.</p>
    );
  }

  function handleMouseMove(e: React.MouseEvent, d: NtcReadCountPoint) {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    setTooltip({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      data: d,
    });
  }

  return (
    <div className="relative">
      <svg ref={svgRef} width={width} height={height} onMouseLeave={() => setTooltip(null)}>
        <Group left={CHART_MARGIN.left} top={CHART_MARGIN.top}>
          <GridRows
            scale={yScale}
            width={innerWidth}
            stroke="#f4f4f5"
            strokeDasharray="3,3"
            numTicks={4}
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
          {points.map((d, i) => (
            <Circle
              key={i}
              cx={xScale(new Date(d.order_date))}
              cy={yScale(d.classified_reads)}
              r={4}
              fill="#3b82f6"
              fillOpacity={0.7}
              style={{ cursor: "pointer" }}
              onMouseMove={(e) => handleMouseMove(e, d)}
            />
          ))}
          <AxisBottom
            top={innerHeight}
            scale={xScale}
            tickValues={weekTicks(xScale.domain()[0], xScale.domain()[1])}
            tickFormat={(d) => `W${isoWeek(d as Date)}`}
            tickStroke="#d1d1d6"
            stroke="#d1d1d6"
            tickLabelProps={{ ...AXIS_TICK_LABEL_PROPS, textAnchor: "middle" }}
          />
          <AxisLeft
            scale={yScale}
            numTicks={4}
            tickFormat={(d) => formatCount(d as number)}
            tickStroke="#d1d1d6"
            stroke="#d1d1d6"
            tickLabelProps={{ ...AXIS_TICK_LABEL_PROPS, textAnchor: "end", dx: -4, dy: 3 }}
          />
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
