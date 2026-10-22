/** A single-series 0-1 trend, with a dashed line at the normal level (0.375). */
export function Sparkline({ values, label }: { values: number[]; label: string }) {
  if (values.length < 2) return null;
  const w = 120;
  const h = 32;
  const x = (i: number) => (i / (values.length - 1)) * w;
  const y = (v: number) => h - v * h;
  const d = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-8 w-[120px]" role="img" aria-label={label}>
      <line x1={0} x2={w} y1={y(0.375)} y2={y(0.375)} style={{ stroke: "var(--axis)" }} strokeDasharray="3 3" />
      <path d={d} fill="none" style={{ stroke: "var(--series-1)" }} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(values.length - 1)} cy={y(values[values.length - 1])} r={2.5} style={{ fill: "var(--series-1)" }} />
    </svg>
  );
}
