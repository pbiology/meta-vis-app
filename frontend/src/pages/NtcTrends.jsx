import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { getNtcTrends } from "../api/ntc";
import { scaleTime, scaleLinear, scaleOrdinal } from "@visx/scale";
import { LinePath, Circle } from "@visx/shape";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { GridRows } from "@visx/grid";
import { Group } from "@visx/group";
import { curveMonotoneX } from "@visx/curve";

// Measures the pixel width of a DOM element, updating on resize.
function useContainerWidth() {
  const [width, setWidth] = useState(0);
  const observerRef = useRef(null);

  const ref = useCallback((node) => {
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

// Colour palette — drawn from Tailwind config accent colours, intentionally
// distinct from the gray/amber/red used for status throughout the app.
const TAXON_COLOURS = [
  "#3b82f6", // blue-500
  "#8b5cf6", // violet-500
  "#10b981", // emerald-500
  "#f59e0b", // amber-500
  "#ef4444", // red-500
  "#06b6d4", // cyan-500
  "#f97316", // orange-500
  "#84cc16", // lime-500
];

const MARGIN = { top: 16, right: 24, bottom: 48, left: 60 };

/** Returns the ISO week number (1–53) for a given date. */
function isoWeek(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d - yearStart) / 86400000 + 1) / 7);
}

/** Generates one Date per week (Mondays) between two dates. */
function weekTicks(minDate, maxDate) {
  const ticks = [];
  const d = new Date(minDate);
  // Advance to next Monday
  d.setDate(d.getDate() + ((1 - d.getDay() + 7) % 7 || 7));
  while (d <= maxDate) {
    ticks.push(new Date(d));
    d.setDate(d.getDate() + 7);
  }
  return ticks;
}

// ---------------------------------------------------------------------------
// Scatter chart — total classified reads per NTC
// ---------------------------------------------------------------------------

function ReadCountChart({ data, width = 600, height = 200 }) {
  const [tooltip, setTooltip] = useState(null);
  const svgRef = useRef(null);

  const points = data.filter((d) => d.order_date && d.classified_reads != null);
  const innerWidth = width - MARGIN.left - MARGIN.right;
  const innerHeight = height - MARGIN.top - MARGIN.bottom;

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

  function handleMouseMove(e, d) {
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
        <Group left={MARGIN.left} top={MARGIN.top}>
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
            tickFormat={(d) => `W${isoWeek(d)}`}
            tickStroke="#d1d1d6"
            stroke="#d1d1d6"
            tickLabelProps={{
              fontSize: 10,
              fill: "#a1a1aa",
              fontFamily: "DM Mono, monospace",
              textAnchor: "middle",
            }}
          />
          <AxisLeft
            scale={yScale}
            numTicks={4}
            tickStroke="#d1d1d6"
            stroke="#d1d1d6"
            tickLabelProps={{
              fontSize: 10,
              fill: "#a1a1aa",
              fontFamily: "DM Mono, monospace",
              textAnchor: "end",
              dx: -4,
              dy: 3,
            }}
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
          <div>{tooltip.data.classified_reads.toLocaleString()} classified reads</div>
          <div className="text-gray-400">{tooltip.data.order_date}</div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Line chart — recurring taxa
// ---------------------------------------------------------------------------

function RecurringTaxaChart({ taxa, width = 600, height = 240 }) {
  const [tooltip, setTooltip] = useState(null);
  const svgRef = useRef(null);

  const allPoints = taxa.flatMap((t) => t.occurrences);
  const innerWidth = width - MARGIN.left - MARGIN.right;
  const innerHeight = height - MARGIN.top - MARGIN.bottom;

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

  const colourScale = scaleOrdinal({
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

  function handleMouseMove(e, d, taxon_name, colour) {
    const rect = svgRef.current.getBoundingClientRect();
    setTooltip({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      data: { ...d, taxon_name, colour },
    });
  }

  return (
    <div className="relative">
      <svg ref={svgRef} width={width} height={height} onMouseLeave={() => setTooltip(null)}>
        <Group left={MARGIN.left} top={MARGIN.top}>
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
                    onMouseMove={(e) => handleMouseMove(e, d, taxon.taxon_name, colour)}
                  />
                ))}
              </g>
            );
          })}
          <AxisBottom
            top={innerHeight}
            scale={xScale}
            tickValues={weekTicks(xScale.domain()[0], xScale.domain()[1])}
            tickFormat={(d) => `W${isoWeek(d)}`}
            tickStroke="#d1d1d6"
            stroke="#d1d1d6"
            tickLabelProps={{
              fontSize: 10,
              fill: "#a1a1aa",
              fontFamily: "DM Mono, monospace",
              textAnchor: "middle",
            }}
          />
          <AxisLeft
            scale={yScale}
            numTicks={4}
            tickStroke="#d1d1d6"
            stroke="#d1d1d6"
            tickLabelProps={{
              fontSize: 10,
              fill: "#a1a1aa",
              fontFamily: "DM Mono, monospace",
              textAnchor: "end",
              dx: -4,
              dy: 3,
            }}
          />
        </Group>
      </svg>

      {/* Legend */}
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
          <div className="text-gray-400">{tooltip.data.case_id}</div>
          <div>{tooltip.data.abundance.toLocaleString()} reads</div>
          <div className="text-gray-400">{tooltip.data.order_date}</div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page shell
// ---------------------------------------------------------------------------

export default function NtcTrends() {
  const [material, setMaterial] = useState("DNA");
  const [windowDays, setWindowDays] = useState(90);
  const [minReads, setMinReads] = useState(3);
  const [minCasePct, setMinCasePct] = useState(10);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [readCountRef, readCountWidth] = useContainerWidth();
  const [recurringRef, recurringWidth] = useContainerWidth();

  useEffect(() => {
    setLoading(true);
    setError(null);
    getNtcTrends({ material, windowDays, minReads, minCasePct: minCasePct / 100 })
      .then(setData)
      .catch(() => setError("Failed to load NTC trends."))
      .finally(() => setLoading(false));
  }, [material, windowDays, minReads, minCasePct]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <h1 className="text-sm font-medium text-gray-900 flex-1">NTC trends</h1>

        {/* Material tabs */}
        <div className="flex items-center gap-1">
          {["DNA", "RNA"].map((m) => (
            <button
              key={m}
              onClick={() => setMaterial(m)}
              className={`px-3 py-1 rounded-full text-xs transition-colors ${
                material === m
                  ? "bg-gray-900 text-white font-medium"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              {m}
            </button>
          ))}
        </div>

        {/* Filter controls */}
        <div className="flex items-center gap-2 border-l border-gray-100 pl-3">
          <span className="text-xs text-gray-400">Min reads</span>
          <select
            value={minReads}
            onChange={(e) => setMinReads(Number(e.target.value))}
            className="text-xs border border-gray-200 rounded-md px-2 py-1 text-gray-600 bg-white focus:outline-none"
          >
            {[1, 3, 5, 10, 20].map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 border-l border-gray-100 pl-3">
          <span className="text-xs text-gray-400">Min cases</span>
          <select
            value={minCasePct}
            onChange={(e) => setMinCasePct(Number(e.target.value))}
            className="text-xs border border-gray-200 rounded-md px-2 py-1 text-gray-600 bg-white focus:outline-none"
          >
            {[5, 10, 20, 25, 50].map((v) => (
              <option key={v} value={v}>
                {v}%
              </option>
            ))}
          </select>
        </div>
        {/* Window selector */}
        <div className="flex items-center gap-2 border-l border-gray-100 pl-3">
          <span className="text-xs text-gray-400">Window</span>
          {[30, 90, 180].map((d) => (
            <button
              key={d}
              onClick={() => setWindowDays(d)}
              className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                windowDays === d
                  ? "bg-gray-900 text-white font-medium"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-6">
        {loading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">
            Loading…
          </div>
        )}
        {error && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">{error}</div>
        )}

        {!loading && !error && data && (
          <>
            {/* Summary line */}
            <p className="text-xs text-gray-400">
              {data.total_ntcs} {material} NTC
              {data.total_ntcs !== 1 ? "s" : ""} in the last {windowDays} days
              {data.recurring_taxa.length > 0 ? (
                <span className="text-amber-500 font-medium ml-1">
                  · {data.recurring_taxa.length} recurring taxon
                  {data.recurring_taxa.length !== 1 ? "a" : ""}
                </span>
              ) : (
                <span className="text-green-500 font-medium ml-1">· no recurring taxa</span>
              )}
            </p>

            {/* Total classified reads */}
            <section ref={readCountRef} className="bg-white border border-gray-100 rounded-xl p-4">
              <h2 className="text-xs font-medium text-gray-600 mb-3">Total classified reads</h2>
              <p className="text-xs text-gray-400 mb-3">
                Each dot is one NTC. Dashed line at 1 000 reads.
              </p>
              {readCountWidth > 0 && (
                <ReadCountChart data={data.read_counts} width={readCountWidth - 32} />
              )}
            </section>

            {/* Recurring taxa */}
            <section ref={recurringRef} className="bg-white border border-gray-100 rounded-xl p-4">
              <div className="flex items-center justify-between mb-1">
                <h2 className="text-xs font-medium text-gray-600">Recurring taxa</h2>
                <span className="text-xs text-gray-400">
                  ≥ {minCasePct}% of cases · &gt; {minReads} reads · kraken2
                </span>
              </div>
              <p className="text-xs text-gray-400 mb-3">
                Taxa present in ≥ {data.min_case_count} of {data.total_ntcs} NTCs in this window.
              </p>
              {recurringWidth > 0 && (
                <RecurringTaxaChart taxa={data.recurring_taxa} width={recurringWidth - 32} />
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
