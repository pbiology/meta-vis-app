import { useMemo } from "react";
import { scaleLinear, scaleOrdinal } from "@visx/scale";
import { Circle, LinePath } from "@visx/shape";
import { Group } from "@visx/group";
import { curveMonotoneX } from "@visx/curve";
import type { NtcRecurringTaxon, NtcTaxonOccurrence } from "../../api/types";
import { CHART_MARGIN, TAXON_COLOURS, useDateScale, usePointerTooltip } from "./chartUtils";
import ChartAxes from "./ChartAxes";

type RecurringTooltipData = NtcTaxonOccurrence & {
  taxon_name: string;
  taxon_id: number;
  colour: string;
};

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
  const allPoints = taxa.flatMap((t) => t.occurrences);
  const innerWidth = width - CHART_MARGIN.left - CHART_MARGIN.right;
  const innerHeight = height - CHART_MARGIN.top - CHART_MARGIN.bottom;

  const xScale = useDateScale(allPoints, innerWidth);

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

  const { tooltip, svgRef, onPointerMove, clear } = usePointerTooltip<RecurringTooltipData>();

  if (taxa.length === 0) {
    return (
      <p className="text-xs text-gray-400 text-center py-8">
        No recurring taxa above threshold in this window.
      </p>
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
                {taxon.occurrences.map((d) => (
                  <Circle
                    key={`${d.order_date}-${d.case_id ?? ""}`}
                    cx={xScale(new Date(d.order_date))}
                    cy={yScale(d.abundance)}
                    r={3.5}
                    fill={colour}
                    fillOpacity={0.85}
                    style={{ cursor: "pointer" }}
                    onMouseMove={(e) =>
                      onPointerMove(e, {
                        ...d,
                        taxon_name: taxon.taxon_name,
                        taxon_id: taxon.taxon_id,
                        colour,
                      })
                    }
                  />
                ))}
              </g>
            );
          })}
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
