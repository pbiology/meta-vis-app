import { AxisBottom, AxisLeft, type AxisScale } from "@visx/axis";
import { GridRows } from "@visx/grid";
import { AXIS_TICK_LABEL_PROPS, formatCount, isoWeek, weekTicks } from "./chartUtils";

interface ChartAxesProps {
  xScale: AxisScale<number>;
  yScale: AxisScale<number>;
  innerWidth: number;
  innerHeight: number;
}

// GridRows + week-tick X axis + count-formatted Y axis. Shared across the three
// NTC trends charts so axis styling stays consistent.
export default function ChartAxes({
  xScale,
  yScale,
  innerWidth,
  innerHeight,
}: Readonly<ChartAxesProps>) {
  return (
    <>
      <GridRows
        scale={yScale}
        width={innerWidth}
        stroke="#f4f4f5"
        strokeDasharray="3,3"
        numTicks={4}
      />
      <AxisBottom
        top={innerHeight}
        scale={xScale}
        tickValues={weekTicks(xScale.domain()[0] as Date, xScale.domain()[1] as Date)}
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
    </>
  );
}
