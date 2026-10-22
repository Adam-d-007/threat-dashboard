import { useMemo, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis,
  YAxis,
} from "recharts";
import { Segmented } from "../components/ui";
import { useLang } from "../i18n";
import type { TimeseriesRow } from "../types/run";
import { useChartColors, type ChartColors } from "./colors";

type Range = "30" | "90" | "365" | "all";
const DAY = 86_400_000;

/** Index over time for one region, with the four level bands shaded and the official level
 * drawn as a dashed line through the middle of its band. */
export function IndexHistory({ rows, officialLevel }: { rows: TimeseriesRow[]; officialLevel: number | null }) {
  const { t, locale } = useLang();
  const c = useChartColors();
  const [range, setRange] = useState<Range>("90");
  const data = useMemo(() => {
    const pts = rows.map((r) => ({ x: new Date(r.at).getTime(), index: r.index, level: r.level }));
    if (range === "all" || pts.length === 0) return pts;
    const end = pts[pts.length - 1].x;
    return pts.filter((p) => p.x >= end - Number(range) * DAY);
  }, [rows, range]);

  const fmtDay = (x: number) => new Date(x).toLocaleDateString(locale, { day: "numeric", month: "short" });
  const bands = [0, 25, 50, 75].map((y, i) => ({ y1: y, y2: y + 25, color: c[`level-${i + 1}` as keyof ChartColors] }));

  return (
    <div>
      <div className="mb-3">
        <Segmented
          label={t.history}
          value={range}
          onChange={setRange}
          options={(["30", "90", "365", "all"] as Range[]).map((r) => ({ value: r, label: t.ranges[r] }))}
        />
      </div>
      <div className="h-64 sm:h-72" role="img" aria-label={t.history}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            {bands.map((b) => (
              <ReferenceArea key={b.y1} y1={b.y1} y2={b.y2} fill={b.color} fillOpacity={0.07} stroke="none" ifOverflow="hidden" />
            ))}
            <CartesianGrid stroke={c.grid} vertical={false} />
            <XAxis
              dataKey="x"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              tickFormatter={fmtDay}
              stroke={c.axis}
              tick={{ fill: c.muted, fontSize: 12 }}
              minTickGap={40}
            />
            <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} stroke={c.axis} tick={{ fill: c.muted, fontSize: 12 }} />
            {officialLevel && (
              <ReferenceLine
                y={(officialLevel - 0.5) * 25}
                stroke={c["ink-2"]}
                strokeDasharray="5 4"
                label={{ value: `${t.officialLine} ${officialLevel}`, fill: c["ink-2"], fontSize: 12, position: "insideTopLeft" }}
              />
            )}
            <Tooltip
              cursor={{ stroke: c.muted, strokeWidth: 1 }}
              contentStyle={{ background: c.surface, border: `1px solid ${c.grid}`, borderRadius: 8, color: c.ink }}
              labelFormatter={(x) => new Date(Number(x)).toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" })}
              formatter={(v, _n, p) => [`${v} (${t.levelWord} ${p.payload.level})`, t.index]}
            />
            <Line type="monotone" dataKey="index" stroke={c["series-1"]} strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
