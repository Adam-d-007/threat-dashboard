import { lazy, Suspense, useMemo, useState } from "react";
import { Card, Muted } from "../components/ui";
import { useLang } from "../i18n";
import { fmtDate } from "../lib/format";
import type { Event, Item } from "../types/run";

const IncidentMap = lazy(() => import("../map/IncidentMap"));

type Filters = { minSeverity: number; type: string; ideology: string; corroboratedOnly: boolean };
type SortKey = "date" | "severity" | "sources";

/** Map, table and ideology mix share one set of filters, shown once above them. */
export function Incidents({
  events,
  items,
  center,
  zoom,
  asOf,
}: {
  events: Event[];
  items: Item[];
  center: [number, number];
  zoom: number;
  /** The run's finish time: the 90-day window counts back from it, not from the viewer's clock. */
  asOf: string;
}) {
  const { t } = useLang();
  const [f, setF] = useState<Filters>({ minSeverity: 0, type: "", ideology: "", corroboratedOnly: false });
  const shown = useMemo(
    () =>
      events.filter(
        (e) =>
          e.severity >= f.minSeverity &&
          (!f.type || e.event_type === f.type) &&
          (!f.ideology || e.ideology === f.ideology) &&
          (!f.corroboratedOnly || e.corroborated),
      ),
    [events, f],
  );
  const select = "rounded-lg border border-line bg-surface-2 px-2 py-1.5 text-sm text-ink";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-sm text-ink-2">
          {t.minSeverity}
          <select className={select} value={f.minSeverity} onChange={(e) => setF({ ...f, minSeverity: Number(e.target.value) })}>
            {[0, 1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <select className={select} aria-label={t.tableCols.type} value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>
          <option value="">{t.allTypes}</option>
          {Object.entries(t.eventTypes).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <select className={select} aria-label={t.tableCols.ideology} value={f.ideology} onChange={(e) => setF({ ...f, ideology: e.target.value })}>
          <option value="">{t.allIdeologies}</option>
          {Object.entries(t.ideologies).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-ink-2">
          <input type="checkbox" checked={f.corroboratedOnly} onChange={(e) => setF({ ...f, corroboratedOnly: e.target.checked })} />
          {t.corroboratedOnly}
        </label>
      </div>

      <Card title={t.map}>
        <Suspense fallback={<div className="h-80 rounded-lg bg-surface-2 sm:h-96" />}>
          <IncidentMap events={shown} center={center} zoom={zoom} />
        </Suspense>
      </Card>

      <Card title={`${t.table} (${shown.length})`}>
        <IncidentTable events={shown} items={items} />
      </Card>

      <Card title={t.ideologyMix}>
        <IdeologyMix events={events} asOf={asOf} />
      </Card>
    </div>
  );
}

function IncidentTable({ events, items }: { events: Event[]; items: Item[] }) {
  const { t, pick, locale } = useLang();
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "date", desc: true });
  const urlOf = new Map(items.map((i) => [i.id, i.url]));
  const rows = [...events].sort((a, b) => {
    const v =
      sort.key === "date"
        ? a.date.localeCompare(b.date)
        : sort.key === "severity"
          ? a.severity - b.severity
          : a.domains.length - b.domains.length;
    return sort.desc ? -v : v;
  });
  if (rows.length === 0) return <Muted>{t.noEvents}</Muted>;

  const th = (key: SortKey | null, label: string, right = false) => (
    <th scope="col" className={`px-2 py-2 font-medium text-muted ${right ? "text-right" : "text-left"}`}>
      {key ? (
        <button type="button" onClick={() => setSort({ key, desc: sort.key === key ? !sort.desc : true })} className="hover:text-ink">
          {label} {sort.key === key ? (sort.desc ? "↓" : "↑") : ""}
        </button>
      ) : (
        label
      )}
    </th>
  );

  return (
    <div className="-mx-4 overflow-x-auto sm:mx-0">
      <table className="w-full min-w-[720px] text-sm">
        <thead className="border-b border-line">
          <tr>
            {th("date", t.tableCols.date)}
            {th(null, t.tableCols.place)}
            {th(null, t.tableCols.type)}
            {th(null, t.tableCols.ideology)}
            {th("severity", t.tableCols.severity, true)}
            {th("sources", t.tableCols.sources, true)}
            {th(null, t.tableCols.corroborated)}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((e) => (
            <tr key={e.id} id={`evt-${e.id}`} className="scroll-mt-24 align-top target:bg-surface-2">
              <td className="whitespace-nowrap px-2 py-2 tabular text-ink-2">{fmtDate(e.date, locale)}</td>
              <td className="px-2 py-2">
                <a href={urlOf.get(e.item_ids[0]) ?? "#"} target="_blank" rel="noreferrer" className="font-medium">
                  {pick(e.title_en, e.title_sk)}
                </a>
                <div className="text-xs text-muted">
                  {e.place?.name ?? e.country} · {e.country}
                </div>
              </td>
              <td className="px-2 py-2 text-ink-2">{t.eventTypes[e.event_type]}</td>
              <td className="px-2 py-2 text-ink-2">{t.ideologies[e.ideology]}</td>
              <td className="px-2 py-2 text-right font-semibold tabular">{e.severity}</td>
              <td className="px-2 py-2 text-right tabular" title={e.domains.join(", ")}>
                {e.domains.length}
              </td>
              <td className="px-2 py-2">
                {e.corroborated ? `✓ ${t.yes}` : t.no}
                {e.has_tier_a && <span className="ml-1 rounded bg-surface-2 px-1 text-xs text-ink-2">A</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Events per TE-SAT ideology category, last 90 days. One series, so one colour and no legend;
 * every bar carries its count, which doubles as the table view. */
function IdeologyMix({ events, asOf }: { events: Event[]; asOf: string }) {
  const { t } = useLang();
  const cutoff = new Date(asOf).getTime() - 90 * 86_400_000;
  const counts = new Map<string, number>();
  for (const e of events) {
    if (new Date(e.date).getTime() >= cutoff) counts.set(e.ideology, (counts.get(e.ideology) ?? 0) + 1);
  }
  const rows = Object.keys(t.ideologies)
    .map((k) => ({ k, n: counts.get(k) ?? 0 }))
    .filter((r) => r.n > 0)
    .sort((a, b) => b.n - a.n);
  if (rows.length === 0) return <Muted>{t.noEvents}</Muted>;
  const max = Math.max(...rows.map((r) => r.n));
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.k} className="grid grid-cols-[minmax(8rem,14rem)_1fr_2rem] items-center gap-3 text-sm">
          <span className="text-ink-2">{t.ideologies[r.k]}</span>
          <span className="h-3 rounded-r" style={{ width: `${(r.n / max) * 100}%`, background: "var(--series-1)" }} />
          <span className="text-right font-semibold tabular">{r.n}</span>
        </li>
      ))}
    </ul>
  );
}
