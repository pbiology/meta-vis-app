import { useMemo, useRef, useState } from "react";
import { scaleLinear, scaleOrdinal, scaleTime } from "@visx/scale";
import { Circle, LinePath } from "@visx/shape";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { GridRows } from "@visx/grid";
import { Group } from "@visx/group";
import { curveMonotoneX } from "@visx/curve";
import type { NtcRecurringTaxon, NtcTaxonOccurrence } from "../../api/types";
import {
  AXIS_TICK_LABEL_PROPS,
  CHART_MARGIN,
  TAXON_COLOURS,
  formatCount,
  isoWeek,
  weekTicks,
} from "./chartUtils";

interface RecurringTooltip {
  x: number;
  y: number;
  data: NtcTaxonOccurrence & { taxon_name: string; taxon_id: number; colour: string };
}

interface RecurringTaxaChartProps {
  taxa: NtcRecurringTaxon[];
  width?: number;
  height?: number;
  isFraction?: boolean;
}

export default function RecurringTaxaChart({
  taxa,
  width = 600,
  height = 240,
  isFraction = false,
}: Readonly<RecurringTaxaChartProps>) {
  const [tooltip, setTooltip] = useState<RecurringTooltip | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const allPoints = taxa.flatMap((t) => t.occurrences);
  const innerWidth = width - CHART_MARGIN.left - CHART_MARGIN.right;
  const innerHeight = height - CHART_MARGIN.top - CHART_MARGIN.bottom;

  const xScale = useMemo(() => {
    const dates = allPoints.map((d) => new Date(d.order_date).getTime());
    const minDate = dates.length ? Math.min(...dates) : Date.now() - 86400000;
    const maxDate = dates.length ? Math.max(...dates) : Date.now();
    return scaleTime({
      domain: [new Date(minDate - 86400000), new Date(maxDate + 86400000)],
      range: [0, innerWidth],
      nice: true,
    });
  }, [allPoints, innerWidth]);

  const yScale = useMemo(() => {
    const maxVal = allPoints.length ? Math.max(...allPoints.map((d) => d.abundance)) : 10;
    return scaleLinear({
      domain: [0, maxVal * 1.1 || 10],
      range: [innerHeight, 0],
      nice: true,
    });
  }, [allPoints, innerHeight]);

  const colourScale = scaleOrdinal<number, string>({
    domain: taxa.map((t) => t.taxon_id),
    range: TAXON_COLOURS,
  });

  if (taxa.length === 0) {
    return (
      <p className="text-xs text-gray-400 text-center py-8">
        No recurring taxa above threshold in this window.
      </p>
    );
  }

  function handleMouseMove(
    e: React.MouseEvent,
    d: NtcTaxonOccurrence,
    taxon_name: string,
    taxon_id: number,
    colour: string
  ) {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    setTooltip({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      data: { ...d, taxon_name, taxon_id, colour },
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
          {taxa.map((taxon) => {
            const colour = colourScale(taxon.taxon_id);
            return (
              <g key={taxon.taxon_id}>
                <LinePath
                  data={taxon.occurrences}
                  x={(d) => xScale(new Date(d.order_date))}
                  y={(d) => yScale(d.abundance)}
                  stroke={colour}
                  strokeWidth={1.5}
                  strokeOpacity={0.8}
                  curve={curveMonotoneX}
                />
                {taxon.occurrences.map((d, i) => (
                  <Circle
                    key={i}
                    cx={xScale(new Date(d.order_date))}
                    cy={yScale(d.abundance)}
                    r={3.5}
                    fill={colour}
                    fillOpacity={0.85}
                    style={{ cursor: "pointer" }}
                    onMouseMove={(e) =>
                      handleMouseMove(e, d, taxon.taxon_name, taxon.taxon_id, colour)
                    }
                  />
                ))}
              </g>
            );
          })}
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

      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 pl-[60px]">
        {taxa.map((taxon) => (
          <div key={taxon.taxon_id} className="flex items-center gap-1.5">
            <span
              className="inline-block w-3 h-0.5 rounded-full"
              style={{ backgroundColor: colourScale(taxon.taxon_id) }}
            />
            <span className="text-xs text-gray-500 italic">
              {taxon.taxon_name.replace(/-/g, " ")}
            </span>
            <span className="text-xs text-gray-300">{taxon.case_count}×</span>
          </div>
        ))}
      </div>

      {tooltip && (
        <div
          className="absolute pointer-events-none bg-white border border-gray-200 rounded-lg shadow-sm px-2.5 py-1.5 text-xs font-mono text-gray-700"
          style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}
        >
          <div className="font-medium italic" style={{ color: tooltip.data.colour }}>
            {tooltip.data.taxon_name.replace(/-/g, " ")}
          </div>
          <div className="text-gray-400">taxid:{tooltip.data.taxon_id}</div>
          <div className="text-gray-400">{tooltip.data.case_id}</div>
          <div>
            {isFraction
              ? `${(tooltip.data.abundance * 100).toFixed(2)}% abundance`
              : `${tooltip.data.abundance.toLocaleString()} reads`}
          </div>
          <div className="text-gray-400">{tooltip.data.order_date}</div>
        </div>
      )}
    </div>
  );
}
