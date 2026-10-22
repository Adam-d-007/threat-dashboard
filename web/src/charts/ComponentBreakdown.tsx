import { useState } from "react";
import { useLang } from "../i18n";
import type { Component, Event } from "../types/run";
import { COMPONENT_SERIES } from "./colors";

/** The four components as weighted contributions that add up to the index: one stacked bar,
 * then a row per component that expands to its inputs and the events behind it. */
export function ComponentBreakdown({ components, index, events }: { components: Component[]; index: number; events: Event[] }) {
  const { t, pick } = useLang();
  const [open, setOpen] = useState<string | null>(null);
  const points = (c: Component) => (c.value === null ? 0 : c.weight * c.value * 100);
  const total = components.reduce((s, c) => s + points(c), 0);
  const byId = new Map(events.map((e) => [e.id, e]));

  return (
    <div>
      <div className="mb-1 flex h-4 w-full gap-[2px] overflow-hidden rounded" aria-hidden>
        {components.map((c) => (
          <div
            key={c.id}
            style={{ width: `${points(c)}%`, background: `var(--${COMPONENT_SERIES[c.id]})` }}
            className="h-full first:rounded-l last:rounded-r"
          />
        ))}
        <div className="h-full flex-1 bg-surface-2" />
      </div>
      <div className="mb-4 flex justify-between text-xs text-muted tabular">
        <span>0</span>
        <span>
          Σ {total.toFixed(1)} → {t.index} {index}
        </span>
        <span>100</span>
      </div>
      <ul className="divide-y divide-line">
        {components.map((c) => {
          const expanded = open === c.id;
          return (
            <li key={c.id}>
              <button
                type="button"
                aria-expanded={expanded}
                onClick={() => setOpen(expanded ? null : c.id)}
                className="flex w-full items-center gap-3 py-2.5 text-left hover:bg-surface-2/60"
              >
                <span className="h-3 w-3 shrink-0 rounded-sm" style={{ background: `var(--${COMPONENT_SERIES[c.id]})` }} aria-hidden />
                <span className="flex-1 font-medium">{t.componentNames[c.id]}</span>
                <span className="text-sm text-muted tabular">
                  {t.value} {c.value === null ? "–" : c.value.toFixed(2)} × {t.weight} {c.weight.toFixed(2)}
                </span>
                <span className="w-20 text-right font-semibold tabular">
                  {points(c).toFixed(1)} <span className="text-xs font-normal text-muted">{t.points}</span>
                </span>
                <span className="text-muted" aria-hidden>{expanded ? "▾" : "▸"}</span>
              </button>
              {expanded && (
                <div className="mb-3 ml-6 space-y-2 rounded-lg bg-surface-2 p-3 text-sm">
                  <p className="text-ink-2">{t.componentHelp[c.id]}</p>
                  {Object.keys(c.inputs).length > 0 && (
                    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 tabular">
                      {Object.entries(c.inputs).map(([k, v]) => (
                        <div key={k} className="contents">
                          <dt className="text-muted">{k.replaceAll("_", " ")}</dt>
                          <dd>{String(v)}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                  {c.event_ids.length > 0 && (
                    <div>
                      <p className="mb-1 text-muted">{t.basedOn}:</p>
                      <ul className="list-disc space-y-0.5 pl-5">
                        {c.event_ids.map((id) => {
                          const e = byId.get(id);
                          return (
                            <li key={id}>
                              <a href={`#evt-${id}`} onClick={(ev) => { ev.preventDefault(); document.getElementById(`evt-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }); }}>
                                {e ? pick(e.title_en, e.title_sk) : id}
                              </a>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
