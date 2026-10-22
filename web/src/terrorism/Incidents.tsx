import { lazy, Suspense, useMemo, useState } from "react";
import { ArticleLink, Card, Muted, Segmented } from "../components/ui";
import { useLang } from "../i18n";
import { fmtDate } from "../lib/format";
import type { Event, Item, Tesat } from "../types/run";

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
  tesat,
}: {
  events: Event[];
  items: Item[];
  tesat: Tesat | null;
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
        <IdeologyMix events={events} asOf={asOf} tesat={tesat} />
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
                <ArticleLink href={urlOf.get(e.item_ids[0])} className="font-medium">
                  {pick(e.title_en, e.title_sk)}
                </ArticleLink>
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
// Event types that correspond to TE-SAT's completed, failed and foiled attacks.
const ATTACK_TYPES = new Set(["attack", "attempted_attack", "plot_disrupted"]);

/** Ideology shares of our 90-day events beside Europol TE-SAT's shares for its latest year:
 * attacks against attacks, arrests against arrests. Shares, because the counts differ in
 * scale (90 days of one region against a full year of the EU). */
function IdeologyMix({ events, asOf, tesat }: { events: Event[]; asOf: string; tesat: Tesat | null }) {
  const { t } = useLang();
  const [kind, setKind] = useState<"attacks" | "arrests">("attacks");
  const cutoff = new Date(asOf).getTime() - 90 * 86_400_000;
  const ours = new Map<string, number>();
  for (const e of events) {
    const match = kind === "attacks" ? ATTACK_TYPES.has(e.event_type) : e.event_type === "arrest";
    if (match && new Date(e.date).getTime() >= cutoff) ours.set(e.ideology, (ours.get(e.ideology) ?? 0) + 1);
  }
  const theirs = new Map(Object.entries(tesat ? (kind === "attacks" ? tesat.attacks_by_ideology : tesat.arrests_by_ideology) : {}));
  const oursTotal = [...ours.values()].reduce((a, b) => a + b, 0);
  const theirsTotal = [...theirs.values()].reduce((a, b) => a + b, 0);
  const rows = Object.keys(t.ideologies)
    .map((k) => ({
      k,
      n: ours.get(k) ?? 0,
      m: theirs.get(k),
      a: oursTotal ? (ours.get(k) ?? 0) / oursTotal : 0,
      b: theirsTotal && theirs.has(k) ? (theirs.get(k) ?? 0) / theirsTotal : null,
    }))
    .filter((r) => r.n > 0 || (r.m ?? 0) > 0)
    .sort((x, y) => Math.max(y.a, y.b ?? 0) - Math.max(x.a, x.b ?? 0));
  const pct = (v: number) => `${Math.round(v * 100)} %`;
  const bar = (v: number, color: string) => (
    <span className="block h-2.5 rounded-r" style={{ width: `${Math.max(v * 100, v > 0 ? 1 : 0)}%`, background: color }} />
  );
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          label={t.mix.label}
          value={kind}
          onChange={setKind}
          options={[
            { value: "attacks", label: t.mix.attacks },
            { value: "arrests", label: t.mix.arrests },
          ]}
        />
        <div className="flex flex-wrap gap-4 text-xs text-ink-2">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: "var(--series-1)" }} />
            {t.mix.ours(oursTotal)}
          </span>
          {tesat && (
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: "var(--series-2)" }} />
              {t.mix.theirs(tesat.report_year, tesat.current.data_year, theirsTotal)}
            </span>
          )}
        </div>
      </div>
      {rows.length === 0 ? (
        <Muted>{t.noEvents}</Muted>
      ) : (
        <ul className="space-y-3">
          {rows.map((r) => (
            <li key={r.k} className="grid grid-cols-[minmax(7rem,13rem)_1fr_7.5rem] items-center gap-x-3 text-sm">
              <span className="text-ink-2">{t.ideologies[r.k]}</span>
              <span className="space-y-1" title={`${r.n} / ${oursTotal} · TE-SAT ${r.m ?? "–"} / ${theirsTotal}`}>
                {bar(r.a, "var(--series-1)")}
                {tesat && (r.b === null ? <span className="block h-2.5 text-[10px] leading-none text-muted">{t.mix.notInTesat}</span> : bar(r.b, "var(--series-2)"))}
              </span>
              <span className="text-right text-xs tabular text-ink-2">
                <span className="font-semibold text-ink">{oursTotal ? pct(r.a) : "–"}</span>
                {tesat && ` · ${r.b === null ? "–" : pct(r.b)}`}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted">{t.mix.note}</p>
    </div>
  );
}
