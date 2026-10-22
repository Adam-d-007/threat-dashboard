import { useEffect, useState } from "react";

const NAMES = [
  "ink", "ink-2", "muted", "grid", "axis", "surface", "series-1", "series-2", "series-3",
  "series-4", "level-1", "level-2", "level-3", "level-4",
] as const;
export type ChartColors = Record<(typeof NAMES)[number], string>;

function read(): ChartColors {
  const css = getComputedStyle(document.documentElement);
  return Object.fromEntries(NAMES.map((n) => [n, css.getPropertyValue(`--${n}`).trim()])) as ChartColors;
}

/** Resolved theme colours for SVG charts, refreshed when the theme toggle changes data-theme. */
export function useChartColors(): ChartColors {
  const [colors, setColors] = useState<ChartColors>(read);
  useEffect(() => {
    const obs = new MutationObserver(() => setColors(read()));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);
  return colors;
}

/** Component id to its categorical slot, fixed so a component keeps its colour everywhere. */
export const COMPONENT_SERIES: Record<string, "series-1" | "series-2" | "series-3" | "series-4"> = {
  events: "series-1",
  media: "series-2",
  anchors: "series-3",
  llm: "series-4",
};
